"""Non-exclusive, directional graph roles; never roles inferred from node kind."""


def current(relation, at):
    return (relation.status == "SOURCE_BACKED" and relation.known_at <= at
            and relation.valid_from <= at and (relation.valid_until is None or at < relation.valid_until))


def roles(bundle, node_id, at):
    result = []
    labels = {"COMPETES_WITH": ("COMPETITOR", "COMPETITOR"),
              "BUYS": ("CUSTOMER", "PURCHASED_PRODUCT"),
              "SUPPLIES": ("SUPPLIER", "SUPPLIED_PARTY_OR_PRODUCT"),
              "SELLS": ("PRODUCT_PROVIDER", "SOLD_PRODUCT")}
    for relation in bundle.relationships:
        if relation.type not in labels or node_id not in {relation.from_id, relation.to_id} or not current(relation, at):
            continue
        outgoing = node_id == relation.from_id
        result.append({"role": labels[relation.type][0 if outgoing else 1],
                       "relationship_id": relation.id, "relation_type": relation.type,
                       "counterpart_id": relation.to_id if outgoing else relation.from_id,
                       "scope": relation.scope, "source_ids": sorted({e.source_id for e in relation.evidence})})
    return result
