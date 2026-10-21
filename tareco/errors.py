class TarecoError(Exception):
    """Base class for every error raised by tareco."""


class NodeNotFound(TarecoError, KeyError):
    """A node that is not in the graph was requested."""

    def __str__(self):
        return Exception.__str__(self)


class EdgeNotFound(TarecoError, KeyError):
    """An edge that is not in the graph was requested."""

    def __str__(self):
        return Exception.__str__(self)


class NoPath(TarecoError):
    """There is no path between the two nodes."""


class NotConnected(TarecoError):
    """The algorithm needs a connected graph."""


class HasCycle(TarecoError):
    """The algorithm needs a graph without cycles."""
