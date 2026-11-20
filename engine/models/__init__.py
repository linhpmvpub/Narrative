"""SQLAlchemy ORM mappings and Pydantic input contracts."""

from sqlalchemy.orm import registry

from engine.models.schema_v1 import metadata

mapper_registry = registry(metadata=metadata)


class EntityRecord:
    pass


class RelationshipRecord:
    pass


class NarrativeRecord:
    pass


class NarrativeVersionRecord:
    pass


class NarrativeDriverRecord:
    pass


for cls, table in (
    (EntityRecord, "rie_entities"),
    (RelationshipRecord, "rie_relationships"),
    (NarrativeRecord, "rie_narratives"),
    (NarrativeVersionRecord, "rie_narrative_versions"),
    (NarrativeDriverRecord, "rie_narrative_drivers"),
):
    mapper_registry.map_imperatively(cls, metadata.tables[table])
