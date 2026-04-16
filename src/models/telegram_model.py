from pydantic import BaseModel, Field


class User(BaseModel):
	id: int
	is_bot: bool
	first_name: str
	last_name: str | None = None
	username: str | None = None
	

class Chat(BaseModel):
	id: int
	type_: str = Field(alias="type")
	first_name: str
	last_name: str | None = None
	username: str
	

class Message(BaseModel):
	message_id: int
	date: int
	from_user: User | None = Field(alias="from", default=None)
	text: str
	chat: Chat


class ReactionType(BaseModel):
	type_: str = Field(alias="type")
	emoji: str | None = None
	custom_emoji_id: int | None = None


class ReactionCount(BaseModel):
	type_: ReactionType = Field(alias="type")
	total_count: int = 0

	
class MessageReactionUpdated(BaseModel):
	chat: Chat
	message_id: int
	user: User | None
	date: int
	old_reaction: list[ReactionType]
	new_reaction: list[ReactionType]
	

class MessageReactionCountUpdated(BaseModel):
	chat: Chat
	message_id: int
	date: int
	reactions: list[ReactionCount]


class Update(BaseModel):
	update_id: int
	message: Message
	message_reaction: MessageReactionUpdated | None = None
	message_reaction_count: MessageReactionCountUpdated | None = None
