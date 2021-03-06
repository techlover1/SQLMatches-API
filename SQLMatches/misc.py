# -*- coding: utf-8 -*-

"""
GNU General Public License v3.0 (GPL v3)
Copyright (c) 2020-2020 WardPearce
Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""


from typing import List
from sqlalchemy.sql import select

from .tables import (
    community_type_table,
    product_table
)
from .exceptions import InvalidUploadSize
from .resources import Sessions, Config
from .caches import CommunityCache


async def cache_community_types(community_types: List[str]):
    """Caches community types.

    Parameters
    ----------
    community_types : List[str]
    """

    query = community_type_table.select(
        community_type_table.c.community_type.in_(community_types)
    ).order_by(community_type_table.c.community_type_id.asc())

    last_id = 0
    async for row in Sessions.database.iterate(query):
        last_id = row["community_type_id"]
        Config.community_types[
            row["community_type"]
        ] = row["community_type_id"]

    for community_type in community_types:
        if community_type not in Config.community_types:
            last_id += 1

            await Sessions.database.execute(
                community_type_table.insert().values(
                    community_type_id=last_id,
                    community_type=community_type
                )
            )

            Config.community_types[community_type] = last_id


def amount_to_upload_size(amount: float) -> float:
    """Used to calculate amount paid to upload size.

    Parameters
    ----------
    amount : float

    Returns
    -------
    float

    Raises
    ------
    InvalidUploadSize
    """

    upload_size = round(
        (amount / Config.cost_per_mb) + Config.free_upload_size,
        2
    )

    if upload_size > Config.max_upload_size or upload_size < 1:
        raise InvalidUploadSize()

    return upload_size


async def bulk_scoreboard_expire(community_name: str,
                                 matches: List[str]) -> None:
    """Used to expire multiple scoreboards.

    Parameters
    ----------
    community_name : str
    matches : List[str]
    """

    cache = CommunityCache(community_name)

    for match in matches:
        await (cache.scoreboard(match)).expire()


async def bulk_community_expire(communities: List[str]) -> None:
    """Used to expire communities in bulk.

    Parameters
    ----------
    communities : List[str]
    """

    for community in communities:
        await CommunityCache(community).expire()


async def create_product_and_set(product_name: str) -> None:
    """Used to create and set products.

    Parameters
    ----------
    product_name : str
    """

    product_id = await Sessions.database.fetch_val(
        select([product_table.c.product_id]).select_from(
            product_table
        ).where(
            product_table.c.name == product_name
        )
    )

    if product_id:
        Config.product_id = product_id
    else:
        data = await Sessions.stripe.create_product(name=product_name)

        await Sessions.database.execute(
            product_table.insert().values(
                product_id=data.id,
                name=product_name
            )
        )

        Config.product_id = data.id
