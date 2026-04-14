import hashlib
import logging
import re
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)


import collections.abc


def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def get_message_list(messages, message_id):
    """
    Reconstructs a list of messages in order up to the specified message_id.

    :param message_id: ID of the message to reconstruct the chain
    :param messages: Message history dict containing all messages
    :return: List of ordered messages starting from the root to the given message
    """

    # Find the message by its id
    current_message = messages.get(message_id)

    if not current_message:
        return None

    # Reconstruct the chain by following the parentId links
    message_list = []

    while current_message:
        message_list.insert(
            0, current_message
        )  # Insert the message at the beginning of the list
        parent_id = current_message["parentId"]
        current_message = messages.get(parent_id) if parent_id else None

    return message_list


def get_messages_content(messages: list[dict]) -> str:
    return "\n".join(
        [
            f"{message['role'].upper()}: {get_content_from_message(message)}"
            for message in messages
        ]
    )


def get_last_user_message_item(messages: list[dict]) -> Optional[dict]:
    for message in reversed(messages):
        if message["role"] == "user":
            return message
    return None


def get_content_from_message(message: dict) -> Optional[str]:
    if isinstance(message["content"], list):
        for item in message["content"]:
            if item["type"] == "text":
                return item["text"]
    else:
        return message["content"]
    return None


def get_last_user_message(messages: list[dict]) -> Optional[str]:
    message = get_last_user_message_item(messages)
    if message is None:
        return None
    return get_content_from_message(message)


def get_last_assistant_message_item(messages: list[dict]) -> Optional[dict]:
    for message in reversed(messages):
        if message["role"] == "assistant":
            return message
    return None


def get_last_assistant_message(messages: list[dict]) -> Optional[str]:
    for message in reversed(messages):
        if message["role"] == "assistant":
            return get_content_from_message(message)
    return None


def get_system_message(messages: list[dict]) -> Optional[dict]:
    for message in messages:
        if message["role"] == "system":
            return message
    return None


def remove_system_message(messages: list[dict]) -> list[dict]:
    return [message for message in messages if message["role"] != "system"]


def pop_system_message(messages: list[dict]) -> tuple[Optional[dict], list[dict]]:
    return get_system_message(messages), remove_system_message(messages)


def prepend_to_first_user_message_content(
    content: str, messages: list[dict]
) -> list[dict]:
    for message in messages:
        if message["role"] == "user":
            if isinstance(message["content"], list):
                for item in message["content"]:
                    if item["type"] == "text":
                        item["text"] = f"{content}\n{item['text']}"
            else:
                message["content"] = f"{content}\n{message['content']}"
            break
    return messages


def add_or_update_system_message(content: str, messages: list[dict]):
    """
    Adds a new system message at the beginning of the messages list
    or updates the existing system message at the beginning.

    :param msg: The message to be added or appended.
    :param messages: The list of message dictionaries.
    :return: The updated list of message dictionaries.
    """

    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = f"{content}\n{messages[0]['content']}"
    else:
        # Insert at the beginning
        messages.insert(0, {"role": "system", "content": content})

    return messages


def add_or_update_user_message(content: str, messages: list[dict]):
    """
    Adds a new user message at the end of the messages list
    or updates the existing user message at the end.

    :param msg: The message to be added or appended.
    :param messages: The list of message dictionaries.
    :return: The updated list of message dictionaries.
    """

    if messages and messages[-1].get("role") == "user":
        messages[-1]["content"] = f"{messages[-1]['content']}\n{content}"
    else:
        # Insert at the end
        messages.append({"role": "user", "content": content})

    return messages


def append_or_update_assistant_message(content: str, messages: list[dict]):
    """
    Adds a new assistant message at the end of the messages list
    or updates the existing assistant message at the end.

    :param msg: The message to be added or appended.
    :param messages: The list of message dictionaries.
    :return: The updated list of message dictionaries.
    """

    if messages and messages[-1].get("role") == "assistant":
        messages[-1]["content"] = f"{messages[-1]['content']}\n{content}"
    else:
        # Insert at the end
        messages.append({"role": "assistant", "content": content})

    return messages


def openai_chat_message_template(model: str):
    return {
        "id": f"{model}-{str(uuid.uuid4())}",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "logprobs": None, "finish_reason": None}],
    }


def openai_chat_completion_message_template(
    model: str, message: Optional[str] = None, usage: Optional[dict] = None
) -> dict:
    template = openai_chat_message_template(model)
    template["object"] = "chat.completion"
    if message is not None:
        template["choices"][0]["message"] = {"content": message, "role": "assistant"}
    template["choices"][0]["finish_reason"] = "stop"

    if usage:
        template["usage"] = usage
    return template


def get_gravatar_url(email):
    # Trim leading and trailing whitespace from
    # an email address and force all characters
    # to lower case
    address = str(email).strip().lower()

    # Create a SHA256 hash of the final string
    hash_object = hashlib.sha256(address.encode())
    hash_hex = hash_object.hexdigest()

    # Grab the actual image URL
    return f"https://www.gravatar.com/avatar/{hash_hex}?d=mp"


def calculate_sha256(file):
    sha256 = hashlib.sha256()
    # Read the file in chunks to efficiently handle large files
    for chunk in iter(lambda: file.read(8192), b""):
        sha256.update(chunk)
    return sha256.hexdigest()


def calculate_sha256_string(string):
    # Create a new SHA-256 hash object
    sha256_hash = hashlib.sha256()
    # Update the hash object with the bytes of the input string
    sha256_hash.update(string.encode("utf-8"))
    # Get the hexadecimal representation of the hash
    hashed_string = sha256_hash.hexdigest()
    return hashed_string


def validate_email_format(email: str) -> bool:
    if email.endswith("@localhost"):
        return True

    if not re.match(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$", email):
        return False

    domain = email.split("@")[-1]
    try:
        import dns.exception
        import dns.resolver
    except Exception as exc:
        log.warning(f"Email DNS validation unavailable for domain '{domain}': {exc}")
        return False

    resolver = dns.resolver.Resolver()

    # Prefer MX as primary deliverability signal.
    try:
        mx_records = resolver.resolve(domain, "MX")
        if len(mx_records) > 0:
            return True
    except dns.resolver.NoAnswer:
        pass
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ):
        return False
    except Exception as exc:
        log.warning(f"Email MX lookup failed for domain '{domain}': {exc}")
        return False

    # RFC-compatible fallback: domains without MX can still receive mail via A/AAAA.
    for record_type in ("A", "AAAA"):
        try:
            records = resolver.resolve(domain, record_type)
            if len(records) > 0:
                return True
        except (
            dns.resolver.NoAnswer,
            dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
        ):
            continue
        except Exception as exc:
            log.warning(
                f"Email {record_type} lookup failed for domain '{domain}': {exc}"
            )
            return False

    return False


BLOCKED_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.de",
    "hotmail.com",
    "hotmail.de",
    "outlook.com",
    "outlook.de",
    "live.com",
    "live.de",
    "aol.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "gmx.de",
    "gmx.net",
    "web.de",
    "t-online.de",
    "freenet.de",
    "mail.com",
    "protonmail.com",
    "proton.me",
    "zoho.com",
}


def is_business_email(email: str) -> bool:
    domain = email.split("@")[-1].lower() if "@" in email else ""
    return bool(domain) and domain not in BLOCKED_EMAIL_DOMAINS


def sanitize_filename(file_name):
    # Convert to lowercase
    lower_case_file_name = file_name.lower()

    # Remove special characters using regular expression
    sanitized_file_name = re.sub(r"[^\w\s]", "", lower_case_file_name)

    # Replace spaces with dashes
    final_file_name = re.sub(r"\s+", "-", sanitized_file_name)

    return final_file_name


def extract_folders_after_data_docs(path):
    # Convert the path to a Path object if it's not already
    path = Path(path)

    # Extract parts of the path
    parts = path.parts

    # Find the index of '/data/docs' in the path
    try:
        index_data_docs = parts.index("data") + 1
        index_docs = parts.index("docs", index_data_docs) + 1
    except ValueError:
        return []

    # Exclude the filename and accumulate folder names
    tags = []

    folders = parts[index_docs:-1]
    for idx, _ in enumerate(folders):
        tags.append("/".join(folders[: idx + 1]))

    return tags


def parse_duration(duration: str) -> Optional[timedelta]:
    if duration == "-1" or duration == "0":
        return None

    # Regular expression to find number and unit pairs
    pattern = r"(-?\d+(\.\d+)?)(ms|s|m|h|d|w)"
    matches = re.findall(pattern, duration)

    if not matches:
        raise ValueError("Invalid duration string")

    total_duration = timedelta()

    for number, _, unit in matches:
        number = float(number)
        if unit == "ms":
            total_duration += timedelta(milliseconds=number)
        elif unit == "s":
            total_duration += timedelta(seconds=number)
        elif unit == "m":
            total_duration += timedelta(minutes=number)
        elif unit == "h":
            total_duration += timedelta(hours=number)
        elif unit == "d":
            total_duration += timedelta(days=number)
        elif unit == "w":
            total_duration += timedelta(weeks=number)

    return total_duration

