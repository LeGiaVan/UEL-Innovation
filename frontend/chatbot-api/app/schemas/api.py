from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

Department = Literal["dbcl", "qtts", "pdt", "pns", "hc", "ctsv", "khcn"]
Role = Literal["member", "department_admin"]
Mode = Literal["module_1", "module_2", "module_3", "module_4"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(StrictModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: SecretStr = Field(min_length=1, max_length=256)


class Membership(StrictModel):
    department: Department
    role: Role = "member"


class UserCreate(LoginRequest):
    password: SecretStr = Field(min_length=12, max_length=256)
    memberships: list[Membership] = Field(default_factory=list, max_length=7)


class UserInfo(BaseModel):
    id: str
    username: str
    system_admin: bool
    memberships: list[Membership]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserInfo


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    mode: Mode = "module_1"


class ChatMode(BaseModel):
    id: Mode
    label: str
    bot_name: str
    description: str


class ModesResponse(BaseModel):
    modes: list[ChatMode]


class QAItem(BaseModel):
    id: str
    mode: Mode
    question: str
    answer: str


class ConversationSummary(BaseModel):
    id: str
    conversation_id: str
    mode: Mode
    preview: str
    created_at: str
    updated_at: str


class ConversationList(BaseModel):
    conversations: list[ConversationSummary]


class Message(BaseModel):
    user_message: str
    assistant_response: str
    timestamp: str


class ConversationDetail(BaseModel):
    conversation_id: str
    mode: Mode
    messages: list[Message]


class RoleUpdate(StrictModel):
    role: Role
