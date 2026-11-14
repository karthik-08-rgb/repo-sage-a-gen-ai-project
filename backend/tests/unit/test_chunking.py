from app.services.chunking.code_chunker import CodeChunker
from app.services.parsing.parser import SymbolParser
from app.services.ingestion.filter import should_index_file, detect_language
from pathlib import Path


def test_python_symbol_parsing():
    code = '''
class PaymentProcessor:
    """Handles credit card payments."""
    def __init__(self, api_key: str):
        self.api_key = api_key

    def process_charge(self, amount: float) -> bool:
        return amount > 0

def calculate_tax(subtotal: float) -> float:
    return subtotal * 0.08
'''
    symbols = SymbolParser.parse_symbols(code, "python")
    sym_names = [s.name for s in symbols]
    assert "PaymentProcessor" in sym_names
    assert "process_charge" in sym_names
    assert "calculate_tax" in sym_names

    class_sym = next(s for s in symbols if s.name == "PaymentProcessor")
    assert class_sym.symbol_type == "class"
    assert class_sym.docstring == "Handles credit card payments."


def test_code_aware_chunking():
    code = '''import os
import sys

def func_one():
    return 1

class Service:
    def method_a(self):
        return "a"

    def method_b(self):
        return "b"
'''
    chunker = CodeChunker(max_chunk_size=1000)
    chunks = chunker.chunk_file(code, "app/service.py", "python")
    assert len(chunks) >= 2
    
    symbol_names = [c.symbol_name for c in chunks if c.symbol_name]
    assert "func_one" in symbol_names or "Service" in symbol_names


def test_file_filtering():
    assert should_index_file(Path(".env"), 100000) is False
    assert should_index_file(Path("secrets.json"), 100000) is False
    assert should_index_file(Path("node_modules/pkg/index.js"), 100000) is False
    assert should_index_file(Path("dist/bundle.js"), 100000) is False
    assert should_index_file(Path("app/main.py"), 100000) is True
