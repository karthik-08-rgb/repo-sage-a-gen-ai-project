import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Tree-sitter languages helper
try:
    import tree_sitter_languages as tsl
    TREE_SITTER_AVAILABLE = True
except Exception as e:
    logger.warning(f"tree-sitter-languages not available: {e}")
    tsl = None
    TREE_SITTER_AVAILABLE = False


@dataclass
class CodeSymbol:
    name: str
    symbol_type: str  # class, function, method, interface, struct, module
    start_line: int
    end_line: int
    parent_name: Optional[str] = None
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ParsedFileStructure:
    symbols: List[CodeSymbol]
    imports: List[str]
    dependencies: List[str]  # Imported module names or paths


LANGUAGE_MAP = {
    "python": "python",
    "py": "python",
    "javascript": "javascript",
    "js": "javascript",
    "jsx": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "tsx": "tsx",
    "go": "go",
    "rust": "rust",
    "rs": "rust",
    "java": "java",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "c": "c",
    "h": "c",
    "hpp": "cpp",
}


class SymbolParser:
    """
    AST-based symbol and structure parser powered by Tree-sitter.
    Recognizes classes, functions, methods, interfaces, structs, imports, decorators, and line ranges.
    """

    @classmethod
    def get_canonical_language(cls, language: str) -> Optional[str]:
        lang = (language or "").lower().strip()
        return LANGUAGE_MAP.get(lang, lang if lang in ("python", "javascript", "typescript", "go", "rust", "java", "cpp", "c") else None)

    @classmethod
    def parse_file(cls, content: str, language: str) -> ParsedFileStructure:
        canonical_lang = cls.get_canonical_language(language)
        if not canonical_lang or not TREE_SITTER_AVAILABLE:
            return cls._fallback_parse(content, language)

        try:
            parser = tsl.get_parser(canonical_lang)
            source_bytes = content.encode("utf-8", errors="replace")
            tree = parser.parse(source_bytes)
            return cls._extract_from_tree(tree.root_node, source_bytes, canonical_lang)
        except Exception as e:
            logger.warning(f"Tree-sitter parse failed for language '{language}': {e}. Falling back.")
            return cls._fallback_parse(content, language)

    @classmethod
    def parse_symbols(cls, content: str, language: str) -> List[CodeSymbol]:
        """Convenience method returning just the extracted CodeSymbols."""
        structure = cls.parse_file(content, language)
        return structure.symbols

    @classmethod
    def _extract_from_tree(cls, root_node, source_bytes: bytes, language: str) -> ParsedFileStructure:
        symbols: List[CodeSymbol] = []
        imports: List[str] = []
        dependencies: List[str] = []

        if language == "python":
            cls._extract_python_symbols(root_node, source_bytes, symbols, imports, dependencies)
        elif language in ("javascript", "typescript", "tsx"):
            cls._extract_js_ts_symbols(root_node, source_bytes, symbols, imports, dependencies)
        elif language == "go":
            cls._extract_go_symbols(root_node, source_bytes, symbols, imports, dependencies)
        elif language == "rust":
            cls._extract_rust_symbols(root_node, source_bytes, symbols, imports, dependencies)
        elif language == "java":
            cls._extract_java_symbols(root_node, source_bytes, symbols, imports, dependencies)
        elif language in ("cpp", "c"):
            cls._extract_c_cpp_symbols(root_node, source_bytes, symbols, imports, dependencies)
        else:
            cls._extract_generic_symbols(root_node, source_bytes, symbols, imports, dependencies)

        return ParsedFileStructure(symbols=symbols, imports=imports, dependencies=dependencies)

    @classmethod
    def _get_node_text(cls, node, source_bytes: bytes) -> str:
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    @classmethod
    def _extract_docstring(cls, node, source_bytes: bytes) -> Optional[str]:
        """Extract docstring or comment block if present at the start of block/body."""
        for child in node.children:
            if child.type == "block":
                for block_child in child.children:
                    if block_child.type == "expression_statement":
                        text = cls._get_node_text(block_child, source_bytes).strip()
                        if (text.startswith('"""') and text.endswith('"""')) or (text.startswith("'''") and text.endswith("'''")):
                            return text.strip('"\' \n\t')
                    elif block_child.type == "string":
                        text = cls._get_node_text(block_child, source_bytes).strip()
                        return text.strip('"\' \n\t')
                    elif not block_child.type.startswith("comment"):
                        break
        return None

    # -------------------------------------------------------------------------
    # Python
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_python_symbols(cls, root_node, source_bytes: bytes, symbols: List[CodeSymbol], imports: List[str], dependencies: List[str]):
        for node in root_node.children:
            cls._traverse_python_node(node, source_bytes, symbols, imports, dependencies, parent_name=None, decorators=[])

    @classmethod
    def _traverse_python_node(cls, node, source_bytes: bytes, symbols: List[CodeSymbol], imports: List[str], dependencies: List[str], parent_name: Optional[str] = None, decorators: Optional[List[str]] = None):
        if decorators is None:
            decorators = []

        if node.type == "decorated_definition":
            cur_decorators = []
            target_def = None
            for child in node.children:
                if child.type == "decorator":
                    cur_decorators.append(cls._get_node_text(child, source_bytes).strip())
                elif child.type in ("class_definition", "function_definition"):
                    target_def = child
            if target_def:
                cls._traverse_python_node(target_def, source_bytes, symbols, imports, dependencies, parent_name=parent_name, decorators=cur_decorators)
            return

        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            class_name = cls._get_node_text(name_node, source_bytes) if name_node else "AnonymousClass"
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            docstring = cls._extract_docstring(node, source_bytes)

            symbols.append(CodeSymbol(
                name=class_name,
                symbol_type="class",
                start_line=start_line,
                end_line=end_line,
                parent_name=parent_name,
                docstring=docstring,
                decorators=decorators
            ))

            body_node = node.child_by_field_name("body")
            if body_node:
                for child in body_node.children:
                    cls._traverse_python_node(child, source_bytes, symbols, imports, dependencies, parent_name=class_name)

        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            func_name = cls._get_node_text(name_node, source_bytes) if name_node else "anonymous_func"
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            docstring = cls._extract_docstring(node, source_bytes)
            sym_type = "method" if parent_name else "function"

            symbols.append(CodeSymbol(
                name=func_name,
                symbol_type=sym_type,
                start_line=start_line,
                end_line=end_line,
                parent_name=parent_name,
                docstring=docstring,
                decorators=decorators
            ))

        elif node.type in ("import_statement", "import_from_statement"):
            import_text = cls._get_node_text(node, source_bytes).strip()
            imports.append(import_text)
            # Extract module dependency name
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        dependencies.append(cls._get_node_text(child, source_bytes).split(".")[0])
            elif node.type == "import_from_statement":
                module_node = node.child_by_field_name("module_name")
                if module_node:
                    dependencies.append(cls._get_node_text(module_node, source_bytes).split(".")[0])

    # -------------------------------------------------------------------------
    # JavaScript & TypeScript
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_js_ts_symbols(cls, root_node, source_bytes: bytes, symbols: List[CodeSymbol], imports: List[str], dependencies: List[str]):
        for node in root_node.children:
            cls._traverse_js_ts_node(node, source_bytes, symbols, imports, dependencies, parent_name=None)

    @classmethod
    def _traverse_js_ts_node(cls, node, source_bytes: bytes, symbols: List[CodeSymbol], imports: List[str], dependencies: List[str], parent_name: Optional[str] = None):
        # Unwrap export statements
        if node.type in ("export_statement", "export_default_declaration"):
            for child in node.children:
                if child.type in ("class_declaration", "function_declaration", "interface_declaration", "type_alias_declaration", "lexical_declaration"):
                    cls._traverse_js_ts_node(child, source_bytes, symbols, imports, dependencies, parent_name)
            return

        if node.type in ("class_declaration", "class"):
            name_node = node.child_by_field_name("name")
            class_name = cls._get_node_text(name_node, source_bytes) if name_node else "AnonymousClass"
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            symbols.append(CodeSymbol(
                name=class_name,
                symbol_type="class",
                start_line=start_line,
                end_line=end_line,
                parent_name=parent_name
            ))

            body_node = node.child_by_field_name("body")
            if body_node:
                for child in body_node.children:
                    if child.type == "method_definition":
                        m_name_node = child.child_by_field_name("name")
                        m_name = cls._get_node_text(m_name_node, source_bytes) if m_name_node else "method"
                        symbols.append(CodeSymbol(
                            name=m_name,
                            symbol_type="method",
                            start_line=child.start_point[0] + 1,
                            end_line=child.end_point[0] + 1,
                            parent_name=class_name
                        ))

        elif node.type in ("function_declaration", "generator_function_declaration"):
            name_node = node.child_by_field_name("name")
            func_name = cls._get_node_text(name_node, source_bytes) if name_node else "anonymous"
            symbols.append(CodeSymbol(
                name=func_name,
                symbol_type="function",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                parent_name=parent_name
            ))

        elif node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if_name = cls._get_node_text(name_node, source_bytes) if name_node else "AnonymousInterface"
            symbols.append(CodeSymbol(
                name=if_name,
                symbol_type="interface",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                parent_name=parent_name
            ))

        elif node.type == "type_alias_declaration":
            name_node = node.child_by_field_name("name")
            t_name = cls._get_node_text(name_node, source_bytes) if name_node else "AnonymousType"
            symbols.append(CodeSymbol(
                name=t_name,
                symbol_type="type",
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                parent_name=parent_name
            ))

        elif node.type == "lexical_declaration":
            # const foo = () => ... or const bar = function() ...
            for decl in node.children:
                if decl.type == "variable_declarator":
                    val = decl.child_by_field_name("value")
                    if val and val.type in ("arrow_function", "function_expression"):
                        name_node = decl.child_by_field_name("name")
                        var_name = cls._get_node_text(name_node, source_bytes) if name_node else "anonymous"
                        symbols.append(CodeSymbol(
                            name=var_name,
                            symbol_type="function",
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            parent_name=parent_name
                        ))

        elif node.type == "import_statement":
            import_str = cls._get_node_text(node, source_bytes).strip()
            imports.append(import_str)
            src_node = node.child_by_field_name("source")
            if src_node:
                raw_dep = cls._get_node_text(src_node, source_bytes).strip("'\"")
                dependencies.append(raw_dep)

    # -------------------------------------------------------------------------
    # Go
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_go_symbols(cls, root_node, source_bytes: bytes, symbols: List[CodeSymbol], imports: List[str], dependencies: List[str]):
        for node in root_node.children:
            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                name = cls._get_node_text(name_node, source_bytes) if name_node else "func"
                symbols.append(CodeSymbol(
                    name=name,
                    symbol_type="function",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                ))
            elif node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                name = cls._get_node_text(name_node, source_bytes) if name_node else "method"
                recv_node = node.child_by_field_name("receiver")
                recv_name = cls._get_node_text(recv_node, source_bytes) if recv_node else None
                symbols.append(CodeSymbol(
                    name=name,
                    symbol_type="method",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent_name=recv_name
                ))
            elif node.type == "type_declaration":
                for spec in node.children:
                    if spec.type == "type_spec":
                        name_node = spec.child_by_field_name("name")
                        name = cls._get_node_text(name_node, source_bytes) if name_node else "struct"
                        type_node = spec.child_by_field_name("type")
                        sym_t = "struct" if type_node and type_node.type == "struct_type" else ("interface" if type_node and type_node.type == "interface_type" else "type")
                        symbols.append(CodeSymbol(
                            name=name,
                            symbol_type=sym_t,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1
                        ))
            elif node.type == "import_declaration":
                imports.append(cls._get_node_text(node, source_bytes).strip())

    # -------------------------------------------------------------------------
    # Rust
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_rust_symbols(cls, root_node, source_bytes: bytes, symbols: List[CodeSymbol], imports: List[str], dependencies: List[str]):
        for node in root_node.children:
            if node.type == "function_item":
                name_node = node.child_by_field_name("name")
                name = cls._get_node_text(name_node, source_bytes) if name_node else "fn"
                symbols.append(CodeSymbol(
                    name=name,
                    symbol_type="function",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                ))
            elif node.type in ("struct_item", "enum_item", "trait_item"):
                name_node = node.child_by_field_name("name")
                name = cls._get_node_text(name_node, source_bytes) if name_node else "item"
                sym_type = node.type.replace("_item", "")
                symbols.append(CodeSymbol(
                    name=name,
                    symbol_type=sym_type,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                ))
            elif node.type == "impl_item":
                type_node = node.child_by_field_name("type")
                impl_name = cls._get_node_text(type_node, source_bytes) if type_node else "impl"
                body_node = node.child_by_field_name("body")
                if body_node:
                    for child in body_node.children:
                        if child.type == "function_item":
                            m_name_node = child.child_by_field_name("name")
                            m_name = cls._get_node_text(m_name_node, source_bytes) if m_name_node else "method"
                            symbols.append(CodeSymbol(
                                name=m_name,
                                symbol_type="method",
                                start_line=child.start_point[0] + 1,
                                end_line=child.end_point[0] + 1,
                                parent_name=impl_name
                            ))
            elif node.type == "use_declaration":
                imports.append(cls._get_node_text(node, source_bytes).strip())

    # -------------------------------------------------------------------------
    # Java
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_java_symbols(cls, root_node, source_bytes: bytes, symbols: List[CodeSymbol], imports: List[str], dependencies: List[str]):
        for node in root_node.children:
            if node.type in ("class_declaration", "interface_declaration", "enum_declaration"):
                name_node = node.child_by_field_name("name")
                name = cls._get_node_text(name_node, source_bytes) if name_node else "JavaClass"
                sym_t = "interface" if "interface" in node.type else "class"
                symbols.append(CodeSymbol(
                    name=name,
                    symbol_type=sym_t,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                ))
                body_node = node.child_by_field_name("body")
                if body_node:
                    for child in body_node.children:
                        if child.type in ("method_declaration", "constructor_declaration"):
                            m_name_node = child.child_by_field_name("name")
                            m_name = cls._get_node_text(m_name_node, source_bytes) if m_name_node else "method"
                            symbols.append(CodeSymbol(
                                name=m_name,
                                symbol_type="method",
                                start_line=child.start_point[0] + 1,
                                end_line=child.end_point[0] + 1,
                                parent_name=name
                            ))
            elif node.type == "import_declaration":
                imports.append(cls._get_node_text(node, source_bytes).strip())

    # -------------------------------------------------------------------------
    # C & C++
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_c_cpp_symbols(cls, root_node, source_bytes: bytes, symbols: List[CodeSymbol], imports: List[str], dependencies: List[str]):
        for node in root_node.children:
            if node.type in ("function_definition", "declaration"):
                declarator = node.child_by_field_name("declarator")
                if declarator:
                    decl_name = cls._get_node_text(declarator, source_bytes).split("(")[0].strip()
                    if decl_name:
                        symbols.append(CodeSymbol(
                            name=decl_name,
                            symbol_type="function",
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1
                        ))
            elif node.type in ("class_specifier", "struct_specifier"):
                name_node = node.child_by_field_name("name")
                name = cls._get_node_text(name_node, source_bytes) if name_node else "struct"
                symbols.append(CodeSymbol(
                    name=name,
                    symbol_type="class" if "class" in node.type else "struct",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                ))
            elif node.type == "preproc_include":
                imports.append(cls._get_node_text(node, source_bytes).strip())

    @classmethod
    def _extract_generic_symbols(cls, root_node, source_bytes: bytes, symbols: List[CodeSymbol], imports: List[str], dependencies: List[str]):
        for node in root_node.children:
            if "function" in node.type or "method" in node.type:
                symbols.append(CodeSymbol(
                    name="func",
                    symbol_type="function",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                ))

    # -------------------------------------------------------------------------
    # Fallback AST / Regex for unsupported extensions or syntax errors
    # -------------------------------------------------------------------------
    @classmethod
    def _fallback_parse(cls, content: str, language: str) -> ParsedFileStructure:
        symbols: List[CodeSymbol] = []
        imports: List[str] = []
        dependencies: List[str] = []

        import ast
        if language == "python":
            try:
                tree = ast.parse(content)
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        end_l = getattr(node, "end_lineno", node.lineno)
                        symbols.append(CodeSymbol(name=node.name, symbol_type="class", start_line=node.lineno, end_line=end_l))
                        for ch in node.body:
                            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                ch_end = getattr(ch, "end_lineno", ch.lineno)
                                symbols.append(CodeSymbol(name=ch.name, symbol_type="method", start_line=ch.lineno, end_line=ch_end, parent_name=node.name))
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        end_l = getattr(node, "end_lineno", node.lineno)
                        symbols.append(CodeSymbol(name=node.name, symbol_type="function", start_line=node.lineno, end_line=end_l))
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        if isinstance(node, ast.Import):
                            for n in node.names:
                                dependencies.append(n.name.split(".")[0])
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            dependencies.append(node.module.split(".")[0])
                return ParsedFileStructure(symbols=symbols, imports=imports, dependencies=dependencies)
            except Exception:
                pass

        # Naive line scan fallback
        import re
        lines = content.splitlines()
        for i, line in enumerate(lines, start=1):
            if m := re.match(r"^\s*(?:def|function|class|func)\s+([a-zA-Z0-9_]+)", line):
                symbols.append(CodeSymbol(name=m.group(1), symbol_type="function", start_line=i, end_line=i))

        return ParsedFileStructure(symbols=symbols, imports=imports, dependencies=dependencies)
