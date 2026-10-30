import uuid
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, create_model

from app.core.dependencies import CurrentUser, DbSession, require_permission
from app.schemas.common import ListParams, Page, partial
from app.services.base import CRUDService

ALL_OPERATIONS = frozenset({"list", "get", "create", "update", "delete"})


@dataclass
class Resource:
    """Declarative description of a REST resource backed by one table."""

    path: str  # e.g. "/classes"
    tag: str  # Swagger group
    name: str  # singular, for summaries ("class")
    permission: str  # module; checks "<module>:read" / "<module>:write"
    service: CRUDService
    create_schema: type[BaseModel]
    read_schema: type[BaseModel]
    update_schema: type[BaseModel] | None = None
    filters: dict[str, Any] = field(default_factory=dict)  # query param -> type
    operations: frozenset[str] = ALL_OPERATIONS
    description: str = ""
    # Override when reading must be stricter than "<module>:read" (e.g. other users' data).
    read_permission: str | None = None


def _a(noun: str) -> str:
    return f"{'an' if noun[0].lower() in 'aeiou' else 'a'} {noun}"


def crud_router(res: Resource) -> APIRouter:
    router = APIRouter(prefix=res.path, tags=[res.tag])
    one = _a(res.name)
    many = res.name if res.name.endswith("record") else f"{res.name} record"
    Read, Create = res.read_schema, res.create_schema
    Update = res.update_schema or partial(Create, f"{Read.__name__.removesuffix('Read')}Update")
    Params = create_model(
        f"{Read.__name__.removesuffix('Read')}ListParams",
        __base__=ListParams,
        **{name: (typ | None, None) for name, typ in res.filters.items()},
    )
    can_read = [require_permission(res.read_permission or f"{res.permission}:read")]
    can_write = [require_permission(f"{res.permission}:write")]
    searchable = ", ".join(str(f if isinstance(f, str) else f.key) for f in res.service.search_fields)
    list_doc = res.description + (f"\n\n`search` matches: {searchable}." if searchable else "")
    if res.filters:
        list_doc += "\n\nFilters: " + ", ".join(f"`{f}`" for f in res.filters) + "."

    if "list" in res.operations:

        @router.get("", response_model=Page[Read], dependencies=can_read,
                    summary=f"List {many}s", description=list_doc.strip())
        def list_items(db: DbSession, params: Annotated[Params, Query()]):
            filters = params.model_dump(include=set(res.filters), exclude_none=True)
            items, total = res.service.list(db, params, filters)
            return Page[Read].build([Read.model_validate(i) for i in items], total, params.page, params.size)

    if "get" in res.operations:

        @router.get("/{item_id}", response_model=Read, dependencies=can_read, summary=f"Get {one}")
        def get_item(item_id: uuid.UUID, db: DbSession):
            return Read.model_validate(res.service.get(db, item_id))

    if "create" in res.operations:

        @router.post("", response_model=Read, status_code=status.HTTP_201_CREATED,
                     dependencies=can_write, summary=f"Create {one}")
        def create_item(payload: Create, db: DbSession, user: CurrentUser):  # type: ignore[valid-type]
            return Read.model_validate(res.service.create(db, payload, user))

    if "update" in res.operations:

        def update_item(item_id: uuid.UUID, payload: Update, db: DbSession, user: CurrentUser):  # type: ignore[valid-type]
            return Read.model_validate(res.service.update(db, item_id, payload, user))

        doc = "Send only the fields you want to change. PUT and PATCH behave the same."
        router.add_api_route("/{item_id}", update_item, methods=["PATCH"], response_model=Read,
                             dependencies=can_write, summary=f"Update {one}", description=doc,
                             operation_id=f"patch_{res.path.strip('/').replace('-', '_')}")
        router.add_api_route("/{item_id}", update_item, methods=["PUT"], response_model=Read,
                             dependencies=can_write, summary=f"Update {one} (PUT)", description=doc,
                             operation_id=f"put_{res.path.strip('/').replace('-', '_')}")

    if "delete" in res.operations:
        archive = res.service.repo.soft_delete

        @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=can_write,
                       summary=f"{'Archive' if archive else 'Delete'} {one}",
                       description="Archived (soft-deleted): hidden from lists but kept for history."
                       if archive else "Fails with 409 if other records still reference it.")
        def delete_item(item_id: uuid.UUID, db: DbSession, user: CurrentUser):
            res.service.delete(db, item_id, user)

    return router
