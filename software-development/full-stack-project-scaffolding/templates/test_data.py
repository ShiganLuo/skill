"""
API 测试数据配置 — 测试数据与测试逻辑解耦
复制此文件并修改端点定义以适配新项目
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class TestConfig:
    """测试配置 — 修改此处适配项目"""
    base_url: str = "http://localhost:8080"
    username: str = "admin"
    password: str = "admin123"
    timeout: int = 10


@dataclass
class Endpoint:
    """API端点定义"""
    method: str
    path: str
    description: str
    body: Optional[dict] = None
    requires_auth: bool = True
    expected_code: int = 200
    depends_on: Optional[str] = None  # e.g., "admin.projects.create"


# ============ 端点注册表 ============
# 占位符: {username}, {password}, {refresh_token}, {timestamp},
#          {project_id}, {pipeline_id} 等会被自动替换
ENDPOINTS = {
    "health": Endpoint(
        method="GET",
        path="/api/front/pipelines/list",
        description="服务可达性检查",
        requires_auth=False,
    ),
    "auth.admin_login": Endpoint(
        method="POST",
        path="/api/admin/auth/login",
        description="管理员登录",
        body={"username": "{username}", "password": "{password}"},
        requires_auth=False,
    ),
    "auth.user_info": Endpoint(
        method="GET",
        path="/api/admin/auth/userInfo",
        description="获取当前用户信息",
    ),
    # ... 按需添加更多端点
}


# ============ 测试执行顺序 ============
TEST_ORDER = [
    ["health"],
    ["auth.admin_login", "auth.user_info"],
    # ... 按需添加
]


# ============ 期望值验证 (可选) ============
EXPECTED_RESPONSE_FIELDS = {
    # "auth.admin_login": lambda r: r.get("result", {}).get("accessToken"),
}
