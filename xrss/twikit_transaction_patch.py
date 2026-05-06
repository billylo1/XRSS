"""
Workaround for twikit ClientTransaction failing after X changed their web bundle format.

Upstream: https://github.com/d60/twikit/issues/408
Remove this module when twikit ships an equivalent fix in PyPI.
"""

from __future__ import annotations

import re


def apply_twikit_transaction_patch() -> None:
    import twikit.x_client_transaction.transaction as tx

    tx.ON_DEMAND_FILE_REGEX = re.compile(
        r""",(\d+):["']ondemand\.s["']""",
        flags=(re.VERBOSE | re.MULTILINE),
    )
    tx.ON_DEMAND_HASH_PATTERN = r',{0}:\"([0-9a-f]+)\"'
    tx.INDICES_REGEX = re.compile(
        r"""(\(\w{1,2}\[(\d{1,2})\],\s*16\))+""",
        flags=(re.VERBOSE | re.MULTILINE),
    )

    async def get_indices(self, home_page_response, session, headers):
        key_byte_indices = []
        response = self.validate_response(home_page_response) or self.home_page_response
        response_str = str(response)

        on_demand_file = tx.ON_DEMAND_FILE_REGEX.search(response_str)
        if on_demand_file:
            on_demand_file_index = on_demand_file.group(1)
            hash_regex = re.compile(tx.ON_DEMAND_HASH_PATTERN.format(on_demand_file_index))
            hash_match = hash_regex.search(response_str)
            if hash_match:
                filename = hash_match.group(1)
                on_demand_file_url = (
                    "https://abs.twimg.com/responsive-web/client-web/"
                    f"ondemand.s.{filename}a.js"
                )
                on_demand_file_response = await session.request(
                    method="GET",
                    url=on_demand_file_url,
                    headers=headers,
                )
                key_byte_indices_match = tx.INDICES_REGEX.finditer(
                    str(on_demand_file_response.text)
                )
                for item in key_byte_indices_match:
                    key_byte_indices.append(item.group(2))

        if not key_byte_indices:
            raise Exception("Couldn't get KEY_BYTE indices")
        key_byte_indices = list(map(int, key_byte_indices))
        return key_byte_indices[0], key_byte_indices[1:]

    tx.ClientTransaction.get_indices = get_indices
