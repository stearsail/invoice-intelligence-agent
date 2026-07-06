import invoice_agent


def test_package_imports():
    assert callable(invoice_agent.main)
