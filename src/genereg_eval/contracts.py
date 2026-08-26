"""Small controlled vocabularies shared by data builders and evaluators."""

RELATION_TYPES = ("Activation", "Repression", "Unknown")
OBJECT_KINDS = ("gene", "regulatory_element", "protein", "other")
ABSTRACT_SUPPORT = (
    "ABSTRACT_SUPPORTED",
    "ABSTRACT_UNSUPPORTED",
    "ABSTRACT_AMBIGUOUS",
)
ROUTES = ("AUTO_ACCEPT", "REVIEW", "REJECT")

