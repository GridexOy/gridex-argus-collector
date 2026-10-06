"""K7 (owner 06.10.2026): people and channels come only from pages of the company's domain.

A page of another domain (an event page, a partner, a directory) is kept as a source
- it may confirm the participation - but nobody and no channel is read from it."""

from __future__ import annotations

from argus_collector.discovery import contract as discovery
from argus_collector.walk import service
from argus_collector.walk.state import WalkState


def own_page(state: WalkState, url: str) -> bool:
    """True on the company's domain or its subdomains (or when the job sets no domains)."""
    domains = state.settings.company_domains
    host = discovery.host_of(url)
    if domains is None or not host or discovery.site_domain(host) in domains:
        return True
    if host not in state.foreign_hosts:
        state.foreign_hosts.add(host)
        state.step(service.STEP_FOREIGN, host, url)
    return False
