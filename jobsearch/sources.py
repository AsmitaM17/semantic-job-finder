from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable
from urllib.parse import quote_plus, urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from .models import Job


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "get_text"):
        value = value.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", str(value)).strip()


def fetch_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=12)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def blocked_search_job(source: str, url: str, keyword: str, location: str, reason: str) -> Job:
    return Job(
        title=f"Open live {source} search",
        company=source,
        location=location,
        url=url,
        source=source,
        summary=f"{source} blocked automated fetching ({reason}). Use this live search link.",
    )


def matches(job: Job, keyword: str, location: str) -> bool:
    haystack = job.searchable_text.lower()
    keyword_ok = all(part in haystack for part in keyword.lower().split() if part)
    if not location.strip() or location.lower() in {"any", "all"}:
        return keyword_ok
    location_parts = [part for part in re.split(r"[, ]+", location.lower()) if part]
    location_ok = any(part in haystack for part in location_parts)
    remote_ok = "remote" in location.lower() and "remote" in haystack
    return keyword_ok and (location_ok or remote_ok)


class Source:
    name = "Source"

    def search(self, request) -> Iterable[Job]:
        raise NotImplementedError


class RemoteOKSource(Source):
    name = "RemoteOK"

    def search(self, request) -> Iterable[Job]:
        url = f"https://remoteok.com/remote-{quote_plus(request.keyword).replace('+', '-')}-jobs"
        soup = fetch_soup(url)
        count = 0
        for row in soup.select("tr.job"):
            title = clean(row.get("data-position") or row.select_one("h2"))
            company = clean(row.get("data-company") or row.select_one("h3"))
            link = row.get("data-url") or (row.select_one("a[itemprop='url']") or {}).get("href")
            if not title or not link:
                continue
            job = Job(
                title=title,
                company=company,
                location="Remote",
                url=urljoin("https://remoteok.com", str(link)),
                source=self.name,
                posted=clean(row.select_one("time")),
                summary=clean(row.select_one(".tags")),
            )
            if matches(job, request.keyword, request.location):
                yield job
                count += 1
            if count >= request.max_per_source:
                break


class WeWorkRemotelySource(Source):
    name = "WeWorkRemotely"

    def search(self, request) -> Iterable[Job]:
        url = f"https://weworkremotely.com/remote-jobs/search?term={quote_plus(request.keyword)}"
        soup = fetch_soup(url)
        count = 0
        for item in soup.select("section.jobs li.feature, section.jobs li:not(.view-all)"):
            if item.select_one(".new-listing__header__title"):
                title = clean(item.select_one(".new-listing__header__title"))
                company = clean(item.select_one(".new-listing__company-name"))
                region = clean(item.select_one(".new-listing__company-headquarters"))
                link_el = item.select_one("a")
            else:
                spans = [clean(span) for span in item.select("span") if clean(span)]
                title = spans[1] if len(spans) > 1 else ""
                company = spans[0] if spans else ""
                region = "Remote"
                link_el = item.select_one("a")
            if not title or not link_el:
                continue
            job = Job(
                title=title,
                company=company,
                location=region or "Remote",
                url=urljoin("https://weworkremotely.com", str(link_el.get("href", ""))),
                source=self.name,
                summary="Remote",
            )
            if matches(job, request.keyword, request.location):
                yield job
                count += 1
            if count >= request.max_per_source:
                break


class PythonOrgSource(Source):
    name = "Python.org"

    def search(self, request) -> Iterable[Job]:
        url = f"https://www.python.org/jobs/?q={quote_plus(request.keyword)}"
        soup = fetch_soup(url)
        count = 0
        for listing in soup.select(".list-recent-jobs li"):
            title_el = listing.select_one("h2 a")
            if not title_el:
                continue
            company = clean(listing.select_one(".listing-company-name"))
            location = clean(listing.select_one(".listing-location"))
            job = Job(
                title=clean(title_el),
                company=company,
                location=location,
                url=urljoin("https://www.python.org", str(title_el.get("href", ""))),
                source=self.name,
                posted=clean(listing.select_one("time")),
                summary=clean(listing.select_one(".listing-job-type")),
            )
            if matches(job, request.keyword, request.location):
                yield job
                count += 1
            if count >= request.max_per_source:
                break


class LinkedInSource(Source):
    name = "LinkedIn"

    def search(self, request) -> Iterable[Job]:
        url = "https://www.linkedin.com/jobs/search/?" + urlencode(
            {"keywords": request.keyword, "location": request.location or "India"}
        )
        try:
            soup = fetch_soup(url)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in {401, 403, 429, 999}:
                yield blocked_search_job(self.name, url, request.keyword, request.location, str(exc))
                return
            raise
        count = 0
        cards = soup.select(".base-card, li.jobs-search-results__list-item, li")
        for card in cards:
            title_el = card.select_one(".base-search-card__title, [class*='job-card-list__title']")
            link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
            if not title_el or not link_el:
                continue
            job = Job(
                title=clean(title_el),
                company=clean(card.select_one(".base-search-card__subtitle, [class*='company-name']")),
                location=clean(card.select_one(".job-search-card__location, [class*='job-card-container__metadata']")),
               url=urljoin(
                  "https://in.indeed.com",
                   str(title_el.get("href", ""))
                ),
                source=self.name,
                posted=clean(card.select_one("time")),
                summary="Public LinkedIn jobs result",
            )
            if matches(job, request.keyword, request.location):
                yield job
                count += 1
            if count >= request.max_per_source:
                break
        if count == 0:
            yield blocked_search_job(self.name, url, request.keyword, request.location, "no parseable public cards")


class IndeedSource(Source):
    name = "Indeed"

    def search(self, request) -> Iterable[Job]:
        base_url = "https://in.indeed.com/jobs"
        url = base_url + "?" + urlencode({"q": request.keyword, "l": request.location})
        try:
            soup = fetch_soup(url)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in {401, 403, 429}:
                yield blocked_search_job(self.name, url, request.keyword, request.location, str(exc))
                return
            raise
        count = 0
        cards = soup.select(".job_seen_beacon, .cardOutline, div[data-testid='slider_item']")
        for card in cards:
            title_el = card.select_one("a.jcs-JobTitle, h2.jobTitle a, a[data-jk]")
            if not title_el:
                continue
            job = Job(
                title=clean(title_el),
                company=clean(card.select_one("[data-testid='company-name'], .companyName")),
                location=clean(card.select_one("[data-testid='text-location'], .companyLocation")),
                url=urljoin(
                  "https://in.indeed.com",
                   str(title_el.get("href", ""))
                ),
                source=self.name,
                posted=clean(card.select_one("[data-testid='myJobsStateDate'], .date")),
                summary=clean(card.select_one(".job-snippet, [data-testid='jobsnippet_footer']")),
            )
            if matches(job, request.keyword, request.location):
                yield job
                count += 1
            if count >= request.max_per_source:
                break
        if count == 0:
            yield blocked_search_job(self.name, url, request.keyword, request.location, "no parseable public cards")


class NaukriSource(Source):
    name = "Naukri"

    def search(self, request) -> Iterable[Job]:
        keyword_slug = re.sub(r"[^a-z0-9]+", "-", request.keyword.lower()).strip("-") or "jobs"
        location_slug = re.sub(r"[^a-z0-9]+", "-", request.location.lower()).strip("-") or "india"
        url = f"https://www.naukri.com/{keyword_slug}-jobs-in-{location_slug}"
        try:
            soup = fetch_soup(url)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in {401, 403, 429}:
                yield blocked_search_job(self.name, url, request.keyword, request.location, str(exc))
                return
            raise
                
                
        count = 0
        cards = soup.select("article.jobTuple, .srp-jobtuple-wrapper, div[class*='jobTuple']")
        for card in cards:
            title_el = card.select_one("a.title, a[href*='/job-listings-'], a[href*='job-listings']")
            if not title_el:
                continue
            job = Job(
                title=clean(title_el),
                company=clean(card.select_one(".comp-name, .companyInfo, a.subTitle")),
                location=clean(card.select_one(".locWdth, .location, span[title*='Location']")),
                url=urljoin(
                    "https://www.naukri.com", 
                    str(title_el.get("href", ""))
                ),
                source=self.name,
                posted=clean(card.select_one(".job-post-day, .type")),
                summary=clean(card.select_one(".job-desc, .job-description, .tags-gt")),
            )
            if matches(job, request.keyword, request.location):
                yield job
                count += 1
            if count >= request.max_per_source:
                break
        if count == 0:
            yield blocked_search_job(self.name, url, request.keyword, request.location, "no parseable public cards")


class GlassdoorSource(Source):
    name = "Glassdoor"

    def search(self, request) -> Iterable[Job]:
        url = "https://www.glassdoor.co.in/Job/jobs.htm?" + urlencode(
            {"sc.keyword": request.keyword, "locKeyword": request.location or "India"}
        )
        try:
            soup = fetch_soup(url)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in {401, 403, 429}:
                yield blocked_search_job(self.name, url, request.keyword, request.location, str(exc))
                return
            raise
        count = 0
        cards = soup.select("li[data-test='jobListing'], .JobsList_jobListItem__wjTHv, li")
        for card in cards:
            title_el = card.select_one("[data-test='job-title'], a[href*='/job-listing/']")
            link_el = card.select_one("a[href*='/job-listing/']")
            if not title_el or not link_el:
                continue
            job = Job(
                title=clean(title_el),
                company=clean(card.select_one("[data-test='employer-name'], .EmployerProfile_compactEmployerName__9MGcV")),
                location=clean(card.select_one("[data-test='emp-location'], .JobCard_location__N_iYE")),
               url=urljoin(
                   "https://www.glassdoor.co.in",
                    str(link_el.get("href", ""))
               ),
                source=self.name,
                posted=clean(card.select_one("[data-test='job-age']")),
                summary="Public Glassdoor jobs result",
            )
            if matches(job, request.keyword, request.location):
                yield job
                count += 1
            if count >= request.max_per_source:
                break
        if count == 0:
            yield blocked_search_job(self.name, url, request.keyword, request.location, "no parseable public cards")


class GreenhouseSource(Source):
    name = "Greenhouse"

    def search(self, request) -> Iterable[Job]:
        count = 0
        for board in request.greenhouse_boards:
            board_url = board if board.startswith("http") else f"https://boards.greenhouse.io/{board}"
            soup = fetch_soup(board_url)
            company = clean(soup.select_one("#board_title")) or board.rstrip("/").split("/")[-1]
            for link in soup.select("a[href*='/jobs/']"):
                title = clean(link)
                if not title:
                    continue
                parent = link.find_parent()
                location = clean(parent.select_one(".location")) if parent else ""
                job = Job(
                    title=title,
                    company=company,
                    location=location,
                    url=urljoin(
                        board_url,
                        str(link.get("href", ""))
                    ),
                    source=self.name,
                )
                if matches(job, request.keyword, request.location):
                    yield job
                    count += 1
                if count >= request.max_per_source:
                    return


class LeverSource(Source):
    name = "Lever"

    def search(self, request) -> Iterable[Job]:
        count = 0
        for board in request.lever_boards:
            board_url = board if board.startswith("http") else f"https://jobs.lever.co/{board}"
            soup = fetch_soup(board_url)
            company = board.rstrip("/").split("/")[-1]
            for posting in soup.select(".posting"):
                title_el = posting.select_one(".posting-title h5") or posting.select_one("a")
                link_el = posting.select_one("a")
                title = clean(title_el)
                if not title or not link_el:
                    continue
                job = Job(
                    title=title,
                    company=company,
                    location=clean(posting.select_one(".sort-by-location")),
                    url=urljoin(board_url, 
                                str(link_el.get("href", ""))),
                    source=self.name,
                    summary=clean(posting.select_one(".sort-by-team")),
                )
                if matches(job, request.keyword, request.location):
                    yield job
                    count += 1
                if count >= request.max_per_source:
                    return


class GenericCareerPageSource(Source):
    name = "GenericCareerPage"

    def search(self, request) -> Iterable[Job]:
        count = 0
        for page_url in request.generic_pages:
            soup = fetch_soup(page_url)
            company = re.sub(r"^www\.", "", page_url.split("//")[-1].split("/")[0])
            for link in soup.select("a[href]"):
                text = clean(link)
                href = link.get("href", "")
                combined = f"{text} {href}".lower()
                if not text or not any(word in combined for word in ["job", "career", "apply", "opening"]):
                    continue
                job = Job(
                    title=text[:120],
                    company=company,
                    location="",
                    url=urljoin(page_url, 
                                str(href)),
                    source=self.name,
                    summary="Discovered from career page",
                )
                if matches(replace(job, summary=f"{job.summary} {request.keyword}"), request.keyword, request.location):
                    yield job
                    count += 1
                if count >= request.max_per_source:
                    return


SOURCE_REGISTRY = {
    source.name: source
    for source in [
        LinkedInSource(),
        NaukriSource(),
        IndeedSource(),
        GlassdoorSource(),
        RemoteOKSource(),
        WeWorkRemotelySource(),
        PythonOrgSource(),
        GreenhouseSource(),
        LeverSource(),
        GenericCareerPageSource(),
    ]
}