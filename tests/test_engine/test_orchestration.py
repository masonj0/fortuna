from python_service.engine import OddsEngine


def test_engine_instantiation():
    """Tests that the core OddsEngine can be instantiated without errors."""
    try:
        engine = OddsEngine()
        assert engine is not None
        assert isinstance(engine, OddsEngine)
    except Exception as e:
        assert False, f"OddsEngine instantiation failed with an exception: {e}"
