"""K7 (owner 06.10.2026): which domains a job may read people and channels from."""

from __future__ import annotations

from argus_collector.discovery import contract as discovery
from argus_collector.scheduler import service


def test_registrable_domain_of_a_host() -> None:
    assert discovery.site_domain("industryx.dimecc.com") == "dimecc.com"
    assert discovery.site_domain("www.reimax.fi") == "reimax.fi"
    assert discovery.site_domain("shop.example.co.uk") == "example.co.uk"
    assert discovery.site_domain("elkris.localhost") == "elkris.localhost"
    assert discovery.site_domain("127.0.0.1") == "127.0.0.1"


def test_only_the_company_own_hosts_give_people() -> None:
    approvals = [
        ("elkris.fi", "seed"),
        ("elkris.com", "redirect_from_seed"),
        ("shop.elkris-group.com", "owner_known_url"),
        ("industryx.dimecc.com", "linked_from_contact_section"),
    ]
    domains = service.company_domains(approvals, "www.elkris.fi")
    assert domains == {"elkris.fi", "elkris.com", "elkris-group.com"}
    assert "dimecc.com" not in domains, "an event site approved from a link: a source only"
