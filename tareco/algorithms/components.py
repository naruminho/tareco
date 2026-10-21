from collections import deque


def components(g):
    """Connected components as sets, biggest first. Direction is ignored."""
    seen = set()
    result = []
    for start in g:
        if start in seen:
            continue
        seen.add(start)
        comp = {start}
        queue = deque([start])
        while queue:
            u = queue.popleft()
            for v in g._all_neighbors(u):
                if v not in seen:
                    seen.add(v)
                    comp.add(v)
                    queue.append(v)
        result.append(comp)
    return sorted(result, key=len, reverse=True)


def is_connected(g):
    return len(g) > 0 and len(components(g)) == 1


def strong_components(g):
    """Strongly connected components (Tarjan), biggest first."""
    index = {}
    low = {}
    stack = []
    on_stack = set()
    result = []
    counter = 0
    for root in g:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(g._succ[root]))]
        while work:
            v, it = work[-1]
            descended = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack.add(w)
                    work.append((w, iter(g._succ[w])))
                    descended = True
                    break
                if w in on_stack:
                    low[v] = min(low[v], index[w])
            if descended:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
            if low[v] == index[v]:
                comp = set()
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.add(w)
                    if w == v:
                        break
                result.append(comp)
    return sorted(result, key=len, reverse=True)
