from typing import List, Optional

from .base import ReferenceTableBase, ReferenceTableType
from .query import ReferenceTableFileQuery


class ReferenceTableConfig(ReferenceTableBase):
    """Configuration for a reference table file (static, no date dependency)."""
    id: str
    server_id: str
    available: bool = True
    description: Optional[str] = None
    notes: Optional[str] = None

    def build(self) -> List[ReferenceTableFileQuery]:
        """Build a single query for this static reference table."""
        assert self.filename is not None, "ReferenceTableConfig must have a filename"
        assert self.directory is not None, "ReferenceTableConfig must have a directory"

        query = ReferenceTableFileQuery(table_type=self.table_type)
        query.build_filename(self.filename)
        query.build_directory(self.directory)
        return [query]
