from beyond_the_loop.models.users import Users
from beyond_the_loop.services.loops_service import loops_service

import beyond_the_loop.models.users
import beyond_the_loop.models.companies
import beyond_the_loop.models.domains
import beyond_the_loop.models.models
import beyond_the_loop.models.prompts
from beyond_the_loop.models.models import user_model_bookmark
from beyond_the_loop.models.prompts import user_prompt_bookmark

users = Users.get_users()

for user in users:
    print(f"Syncing user {user.email}")
    loops_service.create_or_update_loops_contact(user)
    print("syncing user success")