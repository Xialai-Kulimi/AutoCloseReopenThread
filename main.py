"""
TagTheGossiper Module for init core. For detailed usages,
 check https://github.com/Xialai-Kulimi/TagTheGossiper/

Copyright (C) 2024  Kulimi

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
from interactions import (
    Extension,
    SlashCommand,
    Task,
    IntervalTrigger,
    listen,
    ThreadChannel,
    GuildPublicThread,
    SlashContext,
    Permissions,
    slash_option,
    OptionType
)
from time import time
from interactions.api.events import Startup, ThreadUpdate
from pydantic import BaseModel
import aiofiles

from rich.console import Console


console = Console()


class GuildConfig(BaseModel):
    inactive_time: int = 60 * 60 * 24


async def load_config(guild_id: int) -> GuildConfig:
    try:
        async with aiofiles.open(generate_path(guild_id), "r") as f:
            config = GuildConfig.model_validate_json(await f.read())
    except FileNotFoundError:
        config = GuildConfig()

    return config


async def save_config(guild_id: int, config: GuildConfig):
    async with aiofiles.open(generate_path(guild_id), "w") as f:
        await f.write(config.model_dump_json(indent=4))


async def is_admin(ctx: SlashContext) -> bool:
    return ctx.author.has_permission(Permissions.ADMINISTRATOR)


def generate_path(guild_id: int):
    return f"{os.path.dirname(__file__)}/{guild_id}_config.json"


class AutoClose(Extension):
    module_base = SlashCommand(
        name="auto_close",
        description="自動關閉被意外開啟，且無活躍訊息的討論串",
        checks=[is_admin],
    )
    
    
    @module_base.subcommand(
        "config",
        sub_cmd_description="設定無活躍的定義",
    )
    @slash_option(
        name="inactive_time",
        description="一個帖子被視為不活躍，其最新的訊息至少需要存在的時間",
        required=False,
        opt_type=OptionType.NUMBER,
    )
    async def config(
        self,
        ctx: SlashContext,
        inactive_time: int = None,
    ):

        config = await load_config(ctx.guild_id)
        if inactive_time:
            config.inactive_time = inactive_time

        await save_config(ctx.guild_id, config)
        await ctx.respond(f"已設定，新的設定如下\n```py\n{config}\n```", ephemeral=True)
    

    async def try_close_thread(self, thread: ThreadChannel):
        if not isinstance(thread, GuildPublicThread):
            return
        if thread.archived:
            return
        if thread.locked:
            return
    
        config = await load_config(thread.guild_id)
        
        if thread.last_message_id is None or \
            thread.get_message(thread.last_message_id).timestamp.timestamp() + config.inactive_time < time():
            await thread.edit(archived=True)
    
    async def try_close_every_thread(self):
        for guild in self.bot.guilds:
            for thread in guild.threads:
                await self.try_close_thread(thread)
        
    @Task.create(IntervalTrigger(minutes=5))
    async def on_every_five_minute(self):
        await self.try_close_every_thread()
        

    @listen(Startup)
    async def on_startup(self, event: Startup):
        await self.try_close_every_thread()
        

    @listen(ThreadUpdate)
    async def on_thread_update(self, event: ThreadUpdate):
        await self.try_close_thread(event.thread)
