import pytest
from services.parser_service.infrastructure.parsers.javascript_parser import JavascriptParser
from services.parser_service.infrastructure.parsers.typescript_parser import TypescriptParser
from services.graph_service.application.dependency_traversal_service import DependencyTraversalService

def test_javascript_parser_extraction():
    parser = JavascriptParser()
    code = """
import express from 'express';
const helper = require('./utils/helper');

class UserService extends BaseService {
    constructor(db) {
        super(db);
        this.db = db;
    }

    async getUser(id) {
        return await this.db.find(id);
    }
}

function processOrder(orderId) {
    const validated = validate(orderId);
    return save(validated);
}

const calculateTotal = (items) => {
    return items.reduce((acc, item) => acc + item.price, 0);
};
"""
    result = parser.parse_file(code, file_path="services/userService.js")
    assert result["language"] == "javascript"
    assert result["file_path"] == "services/userService.js"
    assert len(result["imports"]) >= 2
    import_modules = [imp.get("module") for imp in result["imports"] if imp.get("module")]
    assert "express" in import_modules
    assert "./utils/helper" in import_modules

    assert len(result["classes"]) == 1
    cls = result["classes"][0]
    assert cls["name"] == "UserService"
    assert cls["bases"] == ["BaseService"]
    method_names = [m["name"] for m in cls["methods"]]
    assert "constructor" in method_names
    assert "getUser" in method_names

    func_names = [f["name"] for f in result["functions"]]
    assert "processOrder" in func_names
    assert "calculateTotal" in func_names

    proc_func = next(f for f in result["functions"] if f["name"] == "processOrder")
    proc_calls = [c["name"] for c in proc_func["calls"]]
    assert "validate" in proc_calls


def test_typescript_tsx_parser_extraction():
    parser = TypescriptParser()
    tsx_code = """
import React, { useState } from 'react';
import { Button } from './components/Button';

export interface UserProps {
    id: string;
    name: string;
}

export type Theme = 'dark' | 'light';

export const UserCard: React.FC<UserProps> = ({ id, name }) => {
    const [active, setActive] = useState(false);
    return (
        <div className="card">
            <h1>{name}</h1>
            <Button onClick={() => setActive(!active)}>Click</Button>
        </div>
    );
};

export function fetchProfile(userId: string): Promise<UserProps> {
    return apiCall(`/users/${userId}`);
}
"""
    result = parser.parse_file(tsx_code, file_path="src/components/UserCard.tsx")
    assert result["language"] == "typescript"
    assert result["file_path"] == "src/components/UserCard.tsx"
    
    # Interfaces and types extracted
    class_names = [c["name"] for c in result["classes"]]
    assert "UserProps" in class_names
    assert "Theme" in class_names

    # Functions extracted (both arrow component and regular function)
    func_names = [f["name"] for f in result["functions"]]
    assert "UserCard" in func_names
    assert "fetchProfile" in func_names

    # Imports extracted
    imp_modules = [i.get("module") for i in result["imports"] if i.get("module")]
    assert "react" in imp_modules
    assert "./components/Button" in imp_modules


def test_dependency_traversal_js_relative():
    class DummyRepo:
        def __init__(self):
            self.nodes = {
                "file-a": {"id": "file-a", "type": "File", "name": "App.tsx", "path": "src/App.tsx"},
                "file-b": {"id": "file-b", "type": "File", "name": "Button.tsx", "path": "src/components/Button.tsx"},
                "imp-1": {"id": "imp-1", "type": "Import", "name": "./components/Button", "path": "src/App.tsx"}
            }
            self.edges = {
                "file-a": [{"source_node": "file-a", "target_node": "imp-1", "relationship_type": "IMPORTS"}]
            }

        def get_outbound_edges(self, node_id):
            return self.edges.get(node_id, [])

        def get_nodes_by_repository(self, repo_id):
            return list(self.nodes.values())

        def get_node(self, node_id):
            return self.nodes.get(node_id)

    repo = DummyRepo()
    service = DependencyTraversalService(repo)
    deps = service.get_file_dependencies("file-a", "repo-123")
    assert "file-b" in deps
