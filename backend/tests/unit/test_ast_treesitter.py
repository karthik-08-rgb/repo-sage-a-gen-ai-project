import pytest
from app.services.parsing.parser import SymbolParser
from app.services.chunking.code_chunker import CodeChunker


def test_treesitter_python_classes_and_methods():
    code = """
@decorator_one
@decorator_two(param="val")
class AccountService:
    \"\"\"Service managing user financial accounts.\"\"\"
    def __init__(self, db_client):
        self.db = db_client

    def transfer_funds(self, source_id: str, target_id: str, amount: float) -> bool:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        return True

def audit_log(event: str):
    pass
"""
    res = SymbolParser.parse_file(code, "python")
    syms = {s.name: s for s in res.symbols}

    assert "AccountService" in syms
    assert syms["AccountService"].symbol_type == "class"
    assert syms["AccountService"].start_line == 4
    assert syms["AccountService"].end_line == 12
    assert "@decorator_one" in syms["AccountService"].decorators

    assert "__init__" in syms
    assert syms["__init__"].symbol_type == "method"
    assert syms["__init__"].parent_name == "AccountService"

    assert "transfer_funds" in syms
    assert syms["transfer_funds"].symbol_type == "method"
    assert syms["transfer_funds"].parent_name == "AccountService"

    assert "audit_log" in syms
    assert syms["audit_log"].symbol_type == "function"
    assert syms["audit_log"].parent_name is None


def test_treesitter_typescript_interfaces_and_classes():
    code = """
import { Injectable } from '@angular/core';

export interface UserDTO {
    id: string;
    email: string;
}

export class UserService {
    getUser(id: string): UserDTO {
        return { id, email: 'user@test.dev' };
    }
}

export const createSession = (userId: string) => {
    return userId + '-session';
};
"""
    res = SymbolParser.parse_file(code, "typescript")
    sym_types = {s.name: s.symbol_type for s in res.symbols}

    assert sym_types.get("UserDTO") == "interface"
    assert sym_types.get("UserService") == "class"
    assert sym_types.get("getUser") == "method"
    assert sym_types.get("createSession") == "function"
    assert "@angular/core" in res.dependencies


def test_treesitter_go_structs_and_functions():
    code = """
package main

import "fmt"

type WorkerPool struct {
    size int
}

func (p *WorkerPool) Start() {
    fmt.Println("Started")
}

func StandaloneWorker() {
    fmt.Println("Running")
}
"""
    res = SymbolParser.parse_file(code, "go")
    sym_types = {s.name: s.symbol_type for s in res.symbols}

    assert sym_types.get("WorkerPool") == "struct"
    assert sym_types.get("Start") == "method"
    assert sym_types.get("StandaloneWorker") == "function"


def test_code_aware_chunking_with_boundaries():
    code = """import os
import sys

def helper_one():
    return 1

def helper_two():
    return 2

class Controller:
    def action(self):
        return True
"""
    chunker = CodeChunker(max_chunk_size=500, overlap=50)
    chunks = chunker.chunk_file(code, "app/controller.py", "python")

    # Should separate module header from functions and class
    assert len(chunks) >= 3
    sym_names = [c.symbol_name for c in chunks]
    assert "helper_one" in sym_names
    assert "helper_two" in sym_names
    assert "Controller" in sym_names or "action" in sym_names
