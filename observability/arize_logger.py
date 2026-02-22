"""Arize Phoenix observability — connects to a running Phoenix server and
instruments all Anthropic and OpenAI (Ollama) SDK calls."""

import sys

PHOENIX_ENDPOINT = "http://localhost:6006/v1/traces"


def setup_observability():
    """Register OTLP exporters and instrument LLM SDKs.

    Connects to the already-running Phoenix server at http://localhost:6006.
    Does NOT attempt to launch a new Phoenix process.

    Returns:
        True on success, False if any required package is missing.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        # Build a provider that sends spans to the running Phoenix instance
        provider = TracerProvider()
        exporter = OTLPSpanExporter(endpoint=PHOENIX_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        # Set as the global provider so all instrumentation picks it up
        trace.set_tracer_provider(provider)

        _instrument_anthropic(provider)
        _instrument_openai(provider)

        print(
            f"[Observability] Tracing → Arize Phoenix at http://localhost:6006",
            file=sys.stderr,
        )
        return True

    except ImportError as exc:
        print(
            f"[Observability] Missing package: {exc}. "
            "Run: pip install opentelemetry-exporter-otlp-proto-http",
            file=sys.stderr,
        )
        return False
    except Exception as exc:
        print(f"[Observability] Setup failed: {exc}", file=sys.stderr)
        return False


def _instrument_anthropic(provider):
    """Instrument the Anthropic SDK if available."""
    try:
        from openinference.instrumentation.anthropic import AnthropicInstrumentor
        AnthropicInstrumentor().instrument(tracer_provider=provider)
    except ImportError:
        pass  # Anthropic SDK not installed; skip silently


def _instrument_openai(provider):
    """Instrument the OpenAI SDK (used by Ollama adapter) if available."""
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        OpenAIInstrumentor().instrument(tracer_provider=provider)
    except ImportError:
        pass  # OpenAI SDK not installed; skip silently


def get_tracer():
    """Return an OpenTelemetry tracer for manual span creation."""
    try:
        from opentelemetry import trace
        return trace.get_tracer("buy_side_analyst")
    except ImportError:
        return None
