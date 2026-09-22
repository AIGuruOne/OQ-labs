"""Reference implementation of Contract 5 (the index interface) over corpus/tickets/.

    from capstone.reference_index import build_index, load_index
"""

from capstone.reference_index.bm25 import TicketIndex, build_index, load_index, plant_tags_in

__all__ = ["TicketIndex", "build_index", "load_index", "plant_tags_in"]
