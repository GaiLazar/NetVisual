import json
import re
import urllib.request
import urllib.error
from typing import Any

from . import agent_tools

AVAILABLE_TOOLS_DOCS = """
### AVAILABLE EXECUTABLE SYSTEM ACTIONS & WEB SEARCH:
You can directly control NetVisual and search the live internet to answer questions or fulfill user requests.
If you need to execute an action or search the internet, output the tool command on its own line:
[TOOL: tool_name(param="value")]

Available Tools:
1. search_web(query="...") - Search the live internet for security vulnerabilities, CVEs, unfamiliar port services, malware reports, or technical manuals.
2. run_security_audit() - Run a complete local vulnerability and open sockets audit, returning threats, DNS leak state, and security grade.
3. check_ip(ip="...") - WHOIS and Threat Intelligence lookup for an external IP address.
4. check_dns_leaks() - Audit local DNS resolvers for privacy leaks.
5. run_ping(target="...") - Ping an IP or host to measure reachability and round-trip latency.
6. run_traceroute(target="...") - Trace network hops to a destination.
7. run_port_scan(target="...") - Scan TCP ports on an IP to check open services.
8. start_speedtest() - Trigger multi-stream bandwidth, latency, and jitter speed test.
9. repair_network() - Flush DNS cache, clear ARP tables, and renew network configuration.
10. set_dns(preset="cloudflare"|"google"|"quad9"|"adguard"|"dhcp") - Change system DNS servers.
11. get_wifi() - Get current Wi-Fi SSID, channel metrics, and signal strength.

Only output ONE tool command at a time if needed. You can include a short confirmation message like "סורק עבורך..." or "מחפש באינטרנט...".
"""

def get_network_context() -> str:
    """Collects real-time telemetry snapshot to enrich the AI context."""
    try:
        from . import summary as sm, probes
        s = sm.summary()
        conns = probes.probe_connections().get("connections", [])[:8]
        conn_samples = [
            f"[{c.get('proto')}] {c.get('laddr')}:{c.get('lport')} -> {c.get('raddr')}:{c.get('rport')} ({c.get('state')})"
            for c in conns
        ]
        ctx_lines = [
            f"Host: {s.get('hostname')}",
            f"Self IP: {s.get('self_ip')} | Gateway: {s.get('gateway')} | Subnet: {s.get('subnet')}",
            f"Active Interfaces: {s.get('interfaces')} | Total Active Connections: {s.get('connections')} (TCP Established: {s.get('tcp_established')}) | Neighbors: {s.get('neighbors')}",
            f"Active Sockets Sample: {'; '.join(conn_samples) if conn_samples else 'None active'}"
        ]
        return "\n".join(ctx_lines)
    except Exception:
        return ""


def _call_provider(provider: str, model: str, api_key: str, endpoint: str,
                   full_prompt: str, active_sys: str, network_ctx: str,
                   prompt: str, temperature: float) -> str:
    """Raw invocation to the selected LLM provider."""
    # 1. Ollama (Local)
    if provider == "ollama":
        url = endpoint.rstrip("/") if endpoint else "http://localhost:11434/api/generate"
        if not url.endswith("/api/generate"):
            url = f"{url}/api/generate"

        req_body = json.dumps({
            "model": model or "llama3",
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }).encode('utf-8')
        req = urllib.request.Request(url, data=req_body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=180) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data.get("response", "")

    # 2. Anthropic Claude
    elif provider == "anthropic":
        if not api_key:
            raise ValueError("Anthropic API key is required")
        url = endpoint if endpoint else "https://api.anthropic.com/v1/messages"
        req_body = json.dumps({
            "model": model or "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "system": active_sys,
            "messages": [
                {"role": "user", "content": f"{'Live Network Telemetry:\n' + network_ctx + '\n\n' if network_ctx else ''}{prompt}"}
            ],
            "temperature": temperature
        }).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01'
        }
        req = urllib.request.Request(url, data=req_body, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data["content"][0]["text"]

    # 3. Google Gemini
    elif provider == "google":
        if not api_key:
            raise ValueError("Google Gemini API key is required")
        m = model or "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        req_body = json.dumps({
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": temperature}
        }).encode('utf-8')
        req = urllib.request.Request(url, data=req_body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data["candidates"][0]["content"]["parts"][0]["text"]

    # 4. OpenAI-Compatible Providers
    elif provider in ("openai", "lmstudio", "deepseek", "groq", "mistral", "openrouter", "custom"):
        url = endpoint
        if not url:
            if provider == "openai": url = "https://api.openai.com/v1/chat/completions"
            elif provider == "deepseek": url = "https://api.deepseek.com/chat/completions"
            elif provider == "groq": url = "https://api.groq.com/openai/v1/chat/completions"
            elif provider == "mistral": url = "https://api.mistral.ai/v1/chat/completions"
            elif provider == "openrouter": url = "https://openrouter.ai/api/v1/chat/completions"
            elif provider == "lmstudio": url = "http://localhost:1234/v1/chat/completions"
            else: url = "http://localhost:8000/v1/chat/completions"

        messages = [
            {"role": "system", "content": active_sys},
            {"role": "user", "content": f"{'Live Network Telemetry:\n' + network_ctx + '\n\n' if network_ctx else ''}{prompt}"}
        ]

        req_payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        req_body = json.dumps(req_payload).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        if provider == "openrouter":
            headers['HTTP-Referer'] = 'http://localhost:8730'
            headers['X-Title'] = 'NetVisual Cyber AI'

        req = urllib.request.Request(url, data=req_body, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data["choices"][0]["message"]["content"]

    raise ValueError(f"Unknown provider: {provider}")


def chat(body: dict) -> dict:
    """
    Sends a chat request to the configured LLM provider with autonomous tool execution.
    """
    provider = body.get("provider", "ollama")
    model = body.get("model", "llama3")
    api_key = body.get("api_key", "").strip()
    endpoint = body.get("endpoint", "").strip()
    prompt = body.get("prompt", "")
    system_prompt = body.get("system_prompt", "").strip()
    try:
        temperature = float(body.get("temperature", 0.7))
    except Exception:
        temperature = 0.7
    include_context = body.get("include_context", True)
    custom_context = body.get("context", "")

    # Telemetry Context
    network_ctx = ""
    if include_context:
        network_ctx = custom_context or get_network_context()

    # Base System instruction + Tool capabilities
    default_sys = (
        "You are Cyber AI Assistant, an elite cybersecurity and network intelligence assistant embedded inside NetVisual. "
        "Help the user inspect packets, analyze bandwidth, identify potential security risks, evaluate DNS/ports, and troubleshoot connectivity. "
        "Be concise, insightful, clear, and direct. Format code, IPs, and ports neatly. "
        "Always respond in the exact same language the user uses (e.g. Hebrew or English). "
        "When responding in Hebrew, write natural RTL Hebrew sentences and place English technical terms, commands, and IP addresses in backticks (e.g. `192.168.1.1`, `Wi-Fi`, `TCP`, `DNS`) so they render without bidirectional distortion.\n"
        f"{AVAILABLE_TOOLS_DOCS}"
    )
    active_sys = f"{system_prompt}\n{AVAILABLE_TOOLS_DOCS}" if system_prompt else default_sys

    full_prompt_sections = [f"System Role:\n{active_sys}"]
    if network_ctx:
        full_prompt_sections.append(f"Live Network Telemetry:\n{network_ctx}")
    full_prompt_sections.append(f"User Query:\n{prompt}")
    
    full_prompt = "\n\n".join(full_prompt_sections)

    try:
        # Step 1: Query the model
        first_reply = _call_provider(
            provider, model, api_key, endpoint,
            full_prompt, active_sys, network_ctx, prompt, temperature
        )

        # Step 2: Check if model invoked any tool
        tool_match = re.search(r"\[TOOL:\s*(\w+)\s*(?:\((.*?)\))?\]", first_reply)
        if not tool_match:
            # Check JSON style tool call
            json_match = re.search(r"```(?:tool|action|json)\s*\n?(\{\s*\"tool\".*?\})\s*```", first_reply, re.DOTALL)
            if json_match:
                try:
                    call_obj = json.loads(json_match.group(1))
                    tool_name = call_obj.get("tool")
                    args = call_obj.get("args", {})
                    tool_match = (tool_name, args)
                except Exception:
                    tool_match = None

        if tool_match:
            if isinstance(tool_match, tuple):
                tool_name, args = tool_match
            else:
                tool_name = tool_match.group(1)
                args_str = tool_match.group(2) or ""
                # Parse key="value" or key='value'
                args = {}
                for k, v in re.findall(r'(\w+)\s*=\s*["\']([^"\']*)["\']', args_str):
                    args[k] = v

            # Execute tool
            tool_res = agent_tools.execute_tool_call(tool_name, args)

            # Step 3: Synthesis prompt with real execution results
            synthesis_prompt = (
                f"User Question:\n{prompt}\n\n"
                f"Action Executed:\n{tool_name} with parameters: {json.dumps(args, ensure_ascii=False)}\n\n"
                f"Real-Time Execution Result Data:\n{json.dumps(tool_res, ensure_ascii=False, indent=2)[:3500]}\n\n"
                "Please review the live result data above and provide a complete, direct, and actionable answer to the user in their language. "
                "Do NOT output another [TOOL: ...] command. Summarize the findings clearly."
            )

            synth_full_prompt = f"System Role:\n{active_sys}\n\n{synthesis_prompt}"

            second_reply = _call_provider(
                provider, model, api_key, endpoint,
                synth_full_prompt, active_sys, "", synthesis_prompt, temperature
            )

            return {
                "reply": second_reply,
                "action_executed": {
                    "tool": tool_name,
                    "args": args,
                    "result": tool_res
                }
            }

        return {"reply": first_reply}

    except urllib.error.HTTPError as e:
        err_msg = ""
        try:
            err_data = json.loads(e.read().decode('utf-8'))
            if isinstance(err_data, dict):
                err_msg = err_data.get("error", {}).get("message") or err_data.get("message") or json.dumps(err_data)
        except Exception:
            try:
                err_msg = e.read().decode('utf-8')
            except Exception:
                pass
        return {"error": f"HTTP {e.code} ({e.reason}): {err_msg}".strip()}
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {str(e.reason)}"}
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


def test_connection(body: dict) -> dict:
    provider = body.get("provider", "ollama")
    endpoint = body.get("endpoint", "").strip()
    api_key = body.get("api_key", "").strip()
    
    try:
        # Ollama
        if provider == "ollama":
            url = endpoint.replace("/api/generate", "").rstrip("/") + "/api/tags" if endpoint else "http://localhost:11434/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=6) as res:
                data = json.loads(res.read().decode('utf-8'))
                models = [m.get("name") for m in data.get("models", [])]
                return {"success": True, "models": models, "message": f"Ollama connected. Discovered {len(models)} local models."}

        # Anthropic
        elif provider == "anthropic":
            if not api_key:
                return {"success": False, "message": "API Key required for Anthropic Claude."}
            url = "https://api.anthropic.com/v1/messages"
            req_body = json.dumps({
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "ping"}]
            }).encode('utf-8')
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            }
            req = urllib.request.Request(url, data=req_body, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as res:
                curated = ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
                return {"success": True, "models": curated, "message": "Anthropic Claude connection successful!"}

        # Google Gemini
        elif provider == "google":
            if not api_key:
                return {"success": False, "message": "API key required for Google Gemini."}
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read().decode('utf-8'))
                models = [m.get("name", "").replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
                return {"success": True, "models": models[:25], "message": f"Google Gemini connected. Found {len(models)} models."}

        # OpenAI, LM Studio, DeepSeek, Groq, Mistral, OpenRouter, Custom
        elif provider in ("openai", "lmstudio", "deepseek", "groq", "mistral", "openrouter", "custom"):
            url = ""
            if provider == "lmstudio":
                url = endpoint.replace("/chat/completions", "").rstrip("/") + "/models" if endpoint else "http://localhost:1234/v1/models"
            elif provider == "openai":
                url = "https://api.openai.com/v1/models"
            elif provider == "groq":
                url = "https://api.groq.com/openai/v1/models"
            elif provider == "deepseek":
                url = "https://api.deepseek.com/models"
            elif provider == "mistral":
                url = "https://api.mistral.ai/v1/models"
            elif provider == "openrouter":
                url = "https://openrouter.ai/api/v1/models"
            elif provider == "custom":
                if "/chat/completions" in endpoint:
                    url = endpoint.replace("/chat/completions", "/models")
                else:
                    url = endpoint.rstrip("/") + "/models"

            headers = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            
            req = urllib.request.Request(url, method="GET", headers=headers)
            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read().decode('utf-8'))
                raw_models = data.get("data", [])
                models = [m.get("id") for m in raw_models if isinstance(m, dict) and m.get("id")]
                return {"success": True, "models": models[:40], "message": f"{provider.capitalize()} connected. Discovered {len(models)} models."}

    except urllib.error.HTTPError as e:
        err_msg = ""
        try:
            err_data = json.loads(e.read().decode('utf-8'))
            if isinstance(err_data, dict):
                err_msg = err_data.get("error", {}).get("message") or err_data.get("message") or str(err_data)
        except Exception:
            pass
        return {"success": False, "message": f"HTTP {e.code} Error: {err_msg or e.reason}"}
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}
    
    return {"success": False, "message": "Unknown provider."}
