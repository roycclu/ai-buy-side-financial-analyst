"""Arize Phoenix observability setup — auto-instruments all Anthropic API calls."""

import sys


def setup_observability():
    """Launch Arize Phoenix and instrument the Anthropic SDK.

    Returns:
        The Phoenix session object, or None if Phoenix is not available.
    """
    try:
        import phoenix as px
        from openinference.instrumentation.anthropic import AnthropicInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        session = px.launch_app()

        provider = TracerProvider()
        # Export traces to the local Phoenix collector
        exporter = OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces")
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        AnthropicInstrumentor().instrument(tracer_provider=provider)

        print(
            f"[Observability] Arize Phoenix running at: {session.url}",
            file=sys.stderr,
        )
        return session
    except ImportError:
        print(
            "[Observability] Arize Phoenix not installed — skipping. "
            "Run: pip install arize-phoenix openinference-instrumentation-anthropic",
            file=sys.stderr,
        )
        return None
    except Exception as exc:
        print(f"[Observability] Phoenix setup failed: {exc}", file=sys.stderr)
        return None


def get_tracer():
    """Return an OpenTelemetry tracer for manual span creation."""
    try:
        from opentelemetry import trace
        return trace.get_tracer("buy_side_analyst")
    except ImportError:
        return None
