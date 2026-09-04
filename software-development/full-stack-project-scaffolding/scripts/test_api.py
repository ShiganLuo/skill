#!/usr/bin/env python3
"""
BioPlatform API Test Suite
Comprehensive test for all backend endpoints.

Usage:
    python test_api.py [--base-url URL] [--username USR] [--password PWD]
"""
import argparse
import sys
import time
import requests

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.token = None

    def set_token(self, token: str):
        self.token = token
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.headers.pop("Authorization", None)

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.session.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.session.post(f"{self.base_url}{path}", **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self.session.put(f"{self.base_url}{path}", **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.session.delete(f"{self.base_url}{path}", **kwargs)


# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


class State:
    access_token: str = ""
    refresh_token: str = ""
    project_id: int = 0
    pipeline_id: int = 0


def run_test(category: str, name: str, fn, state: State):
    """Run a single test and print result."""
    try:
        fn(state)
        print(f"  {GREEN}✓ PASS{RESET}  {name}")
        return True
    except Exception as e:
        print(f"  {RED}✗ FAIL{RESET}  {name}  ({e})")
        return False


def assert_success(resp: requests.Response) -> dict:
    """Assert HTTP 200 and API code 200, return body."""
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    body = resp.json()
    assert body.get("code") == 200, f"API code={body.get('code')}, message={body.get('message')}"
    return body


def assert_error(resp: requests.Response) -> dict:
    """Assert non-200 API code, return body."""
    body = resp.json()
    assert body.get("code") != 200, f"Expected error but got code=200"
    return body


def main():
    parser = argparse.ArgumentParser(description="BioPlatform API Test Suite")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()

    client = APIClient(args.base_url)
    state = State()
    results = {"pass": 0, "fail": 0}
    t0 = time.time()

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"  BioPlatform API Test Suite")
    print(f"{'=' * 60}")
    print(f"  Base URL:  {args.base_url}")
    print(f"  User:      {args.username}")
    print(f"  Time:      {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")

    # --- Health ---
    print(f"{BOLD}[Health]{RESET}")

    def _health(s):
        resp = client.get("/api/front/pipelines/list")
        assert resp.status_code == 200
    if run_test("Health", "Server reachable", _health, state):
        results["pass"] += 1
    else:
        results["fail"] += 1
        print(f"\n{RED}Server unreachable, aborting.{RESET}")
        return 1

    # --- Auth ---
    print(f"\n{BOLD}[Auth]{RESET}")

    def _admin_login(s):
        resp = client.post("/api/admin/auth/login", json={"username": args.username, "password": args.password})
        body = assert_success(resp)
        result = body.get("result") or {}
        s.access_token = result.get("accessToken", "")
        s.refresh_token = result.get("refreshToken", "")
        assert s.access_token, "No access token"
        client.set_token(s.access_token)
    for fn, name in [(_admin_login, f"Admin login ({args.username})")]:
        r = run_test("Auth", name, fn, state)
        results["pass" if r else "fail"] += 1

    def _user_info(s):
        resp = client.get("/api/admin/auth/userInfo")
        body = assert_success(resp)
    r = run_test("Auth", "User info", _user_info, state)
    results["pass" if r else "fail"] += 1

    def _refresh_token(s):
        old_token = s.access_token
        client.set_token("")
        resp = client.post("/api/admin/auth/refreshToken", json={"refreshToken": s.refresh_token})
        body = assert_success(resp)
        result = body.get("result") or {}
        new_token = result.get("accessToken") or result.get("token")
        assert new_token, "No new token from refresh"
        client.set_token(old_token)
    r = run_test("Auth", "Refresh token", _refresh_token, state)
    results["pass" if r else "fail"] += 1

    def _front_login(s):
        resp = client.post("/api/front/auth/login", json={"username": args.username, "password": args.password})
        body = assert_success(resp)
        result = body.get("result") or {}
        token = result.get("accessToken") or result.get("token")
        assert token, "No token from front login"
    r = run_test("Auth", "Front auth login", _front_login, state)
    results["pass" if r else "fail"] += 1

    def _unauthorized(s):
        old_token = s.access_token
        client.set_token("invalid-token-12345")
        resp = client.get("/api/admin/auth/userInfo")
        client.set_token(old_token)
        assert resp.status_code == 403 or resp.json().get("code") != 200, "Should have been rejected"
    r = run_test("Auth", "Unauthorized access rejected", _unauthorized, state)
    results["pass" if r else "fail"] += 1

    # --- Public ---
    print(f"\n{BOLD}[Public]{RESET}")
    client.set_token("")
    for path, name in [
        ("/api/front/projects/list", "GET /front/projects/list"),
        ("/api/front/pipelines/list", "GET /front/pipelines/list"),
        ("/api/front/pipelines/categories", "GET /front/pipelines/categories"),
        ("/api/front/agent/tools", "GET /front/agent/tools"),
    ]:
        def _pub(s, p=path):
            resp = client.get(p)
            assert_success(resp)
        r = run_test("Public", name, _pub, state)
        results["pass" if r else "fail"] += 1

    # --- Admin ---
    print(f"\n{BOLD}[Admin]{RESET}")
    client.set_token(state.access_token)

    # Projects
    def _proj_list(s):
        resp = client.get("/api/admin/projects/list", params={"pageNum": 1, "pageSize": 10})
        assert_success(resp)
    r = run_test("Admin", "GET /admin/projects/list", _proj_list, state)
    results["pass" if r else "fail"] += 1

    def _proj_create(s):
        resp = client.post("/api/admin/projects/create", json={"name": "test_project", "description": "auto test", "ownerId": 1})
        body = assert_success(resp)
        result = body.get("result") or {}
        s.project_id = result.get("id", 0)
    r = run_test("Admin", "POST /admin/projects/create", _proj_create, state)
    results["pass" if r else "fail"] += 1

    def _proj_get(s):
        resp = client.get(f"/api/admin/projects/{s.project_id}")
        assert_success(resp)
    r = run_test("Admin", f"GET /admin/projects/{state.project_id}", _proj_get, state)
    results["pass" if r else "fail"] += 1

    def _proj_update(s):
        resp = client.put("/api/admin/projects/update", json={"id": s.project_id, "name": "test_project_updated"})
        assert_success(resp)
    r = run_test("Admin", "PUT /admin/projects/update", _proj_update, state)
    results["pass" if r else "fail"] += 1

    # Pipelines
    def _pipe_list(s):
        resp = client.get("/api/admin/pipelines/list", params={"pageNum": 1, "pageSize": 10})
        assert_success(resp)
    r = run_test("Admin", "GET /admin/pipelines/list", _pipe_list, state)
    results["pass" if r else "fail"] += 1

    def _pipe_create(s):
        resp = client.post("/api/admin/pipelines/create", json={"name": "test_pipeline", "description": "auto test"})
        body = assert_success(resp)
        result = body.get("result") or {}
        s.pipeline_id = result.get("id", 0)
    r = run_test("Admin", "POST /admin/pipelines/create", _pipe_create, state)
    results["pass" if r else "fail"] += 1

    def _pipe_get(s):
        resp = client.get(f"/api/admin/pipelines/{s.pipeline_id}")
        assert_success(resp)
    r = run_test("Admin", f"GET /admin/pipelines/{state.pipeline_id}", _pipe_get, state)
    results["pass" if r else "fail"] += 1

    # Other admin endpoints
    for path, name in [
        ("/api/admin/executions/list?pageNum=1&pageSize=10", "GET /admin/executions/list"),
        ("/api/admin/datafiles/list?projectId=1&pageNum=1&pageSize=10", "GET /admin/datafiles/list"),
        ("/api/admin/users/list?pageNum=1&pageSize=10", "GET /admin/users/list"),
        ("/api/admin/roles/list", "GET /admin/roles/list"),
        ("/api/admin/system/configs", "GET /admin/system/configs"),
        ("/api/admin/system/dashboard", "GET /admin/system/dashboard"),
        ("/api/admin/agent/tools", "GET /admin/agent/tools"),
        ("/api/admin/agent/conversations", "GET /admin/agent/conversations"),
        ("/api/admin/logs/list?pageNum=1&pageSize=10", "GET /admin/logs/list"),
    ]:
        def _ep(s, p=path):
            resp = client.get(p)
            assert_success(resp)
        r = run_test("Admin", name, _ep, state)
        results["pass" if r else "fail"] += 1

    # --- Cleanup ---
    print(f"\n{BOLD}[Cleanup]{RESET}")
    if state.pipeline_id:
        def _pipe_del(s):
            resp = client.delete(f"/api/admin/pipelines/{s.pipeline_id}")
            assert_success(resp)
        r = run_test("Cleanup", f"DELETE /admin/pipelines/{state.pipeline_id}", _pipe_del, state)
        results["pass" if r else "fail"] += 1

    if state.project_id:
        def _proj_del(s):
            resp = client.delete(f"/api/admin/projects/{s.project_id}")
            assert_success(resp)
        r = run_test("Cleanup", f"DELETE /admin/projects/{state.project_id}", _proj_del, state)
        results["pass" if r else "fail"] += 1

    # --- Summary ---
    elapsed = time.time() - t0
    total = results["pass"] + results["fail"]
    print(f"\n{'=' * 60}")
    print(f"  TEST SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total:   {total}")
    print(f"  {GREEN}Passed:  {results['pass']}{RESET}")
    if results["fail"]:
        print(f"  {RED}Failed:  {results['fail']}{RESET}")
    print(f"  Time:    {elapsed:.2f}s")
    print(f"{'=' * 60}\n")

    return 1 if results["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
