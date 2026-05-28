#!/usr/bin/env python3

import argparse
import collections
import os
import sys
import tempfile
from dataclasses import dataclass

try:
    import yaml
except ImportError as error:
    print(
        "This script requires PyYAML. Install python3-yaml in the runtime environment.",
        file=sys.stderr,
    )
    raise SystemExit(1) from error

try:
    import apt_pkg
except ImportError as error:
    print(
        "This script requires python-apt (apt_pkg). Install python3-apt in the runtime environment.",
        file=sys.stderr,
    )
    raise SystemExit(1) from error


BASE_TO_SUITE = {
    "core20": "focal",
    "core22": "jammy",
    "core24": "noble",
    "core26": "resolute",
}

PRIMARY_ARCHITECTURES = {"amd64", "i386"}
MAIN_ARCHIVE_URL = "http://archive.ubuntu.com/ubuntu"
SECURITY_ARCHIVE_URL = "http://security.ubuntu.com/ubuntu"
PORTS_ARCHIVE_URL = "http://ports.ubuntu.com/ubuntu-ports"
COMPONENTS = ("main", "restricted", "universe", "multiverse")
POCKETS = ("", "-updates", "-security", "-backports")
DEPENDENCY_FIELDS = ("Depends", "PreDepends", "Pre-Depends")


@dataclass(frozen=True)
class DependencyEdge:
    parent_name: str
    relation: str
    alternatives: tuple[str, ...]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Explain why a Debian package is staged by tracing dependency chains "
            "from snapcraft.yaml stage-packages."
        )
    )
    parser.add_argument("package", help="Requested Debian binary package name")
    parser.add_argument(
        "--arch",
        default="amd64",
        help="Target architecture to resolve. Defaults to amd64.",
    )
    parser.add_argument(
        "--snapcraft-yaml",
        default=None,
        help="Path to snapcraft.yaml. Defaults to ./snapcraft.yaml or ./snap/snapcraft.yaml.",
    )
    parser.add_argument(
        "--scratch-dir",
        default=None,
        help="Existing or new directory for the isolated APT workspace. Defaults to a new temporary directory.",
    )
    parser.add_argument(
        "--max-chains",
        type=int,
        default=20,
        help="Maximum number of dependency chains to print. Use 0 for no limit.",
    )
    return parser.parse_args()


def resolve_snapcraft_path(cli_path: str | None) -> str:
    if cli_path:
        return cli_path

    for candidate in ("snapcraft.yaml", os.path.join("snap", "snapcraft.yaml")):
        if os.path.exists(candidate):
            return candidate

    raise FileNotFoundError("Could not find snapcraft.yaml in the current directory or in ./snap/")


def load_snapcraft(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def normalize_package_name(package_name: str) -> str:
    return package_name.split(":", 1)[0].strip()


def normalize_architecture_condition(condition: str) -> set[str]:
    condition = condition.strip().lower()
    if not condition.startswith("on "):
        return set()

    normalized = condition[3:].replace(",", " ")
    return {item for item in normalized.split() if item}


def collect_stage_packages(data: dict, architecture: str) -> dict[str, set[str]]:
    roots: dict[str, set[str]] = collections.defaultdict(set)
    for part_name, part in data.get("parts", {}).items():
        stage_packages = part.get("stage-packages", [])
        for package_name, origin in iter_stage_package_entries(stage_packages, part_name, architecture):
            roots[normalize_package_name(package_name)].add(origin)
    return roots


def iter_stage_package_entries(entries, part_name: str, architecture: str, condition: str | None = None):
    if isinstance(entries, str):
        origin = part_name if condition is None else f"{part_name} [{condition}]"
        yield entries, origin
        return

    if isinstance(entries, dict):
        for nested_condition, nested_entries in entries.items():
            allowed_architectures = normalize_architecture_condition(str(nested_condition))
            if allowed_architectures and architecture not in allowed_architectures:
                continue
            yield from iter_stage_package_entries(
                nested_entries,
                part_name,
                architecture,
                condition=str(nested_condition),
            )
        return

    if not isinstance(entries, list):
        return

    for entry in entries:
        if isinstance(entry, str):
            origin = part_name if condition is None else f"{part_name} [{condition}]"
            yield entry, origin
            continue

        if not isinstance(entry, dict):
            continue

        for nested_condition, nested_entries in entry.items():
            allowed_architectures = normalize_architecture_condition(str(nested_condition))
            if allowed_architectures and architecture not in allowed_architectures:
                continue
            yield from iter_stage_package_entries(
                nested_entries,
                part_name,
                architecture,
                condition=str(nested_condition),
            )


def resolve_suite(base_name: str) -> str:
    try:
        return BASE_TO_SUITE[base_name]
    except KeyError as error:
        supported = ", ".join(sorted(BASE_TO_SUITE))
        raise ValueError(
            f"Unsupported snap base {base_name!r}. Extend BASE_TO_SUITE for this script. Supported bases: {supported}"
        ) from error


def build_repository_lines(suite: str, architecture: str) -> list[str]:
    if architecture in PRIMARY_ARCHITECTURES:
        archive_url = MAIN_ARCHIVE_URL
        security_url = SECURITY_ARCHIVE_URL
    else:
        archive_url = PORTS_ARCHIVE_URL
        security_url = PORTS_ARCHIVE_URL

    components = " ".join(COMPONENTS)
    lines = []
    for pocket_suffix in POCKETS:
        pocket = f"{suite}{pocket_suffix}"
        base_url = security_url if pocket_suffix == "-security" else archive_url
        lines.append(f"deb [arch={architecture} trusted=yes] {base_url} {pocket} {components}")
    return lines


def ensure_directory(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def prepare_scratch_workspace(base_directory: str, suite: str, architecture: str) -> dict[str, str]:
    etc_apt = os.path.join(base_directory, "etc", "apt")
    preferences_dir = os.path.join(etc_apt, "preferences.d")
    state_dir = os.path.join(base_directory, "var", "lib", "apt")
    lists_dir = os.path.join(state_dir, "lists")
    cache_dir = os.path.join(base_directory, "var", "cache", "apt")
    archives_dir = os.path.join(cache_dir, "archives")
    dpkg_dir = os.path.join(base_directory, "var", "lib", "dpkg")

    for path in (
        etc_apt,
        preferences_dir,
        os.path.join(etc_apt, "sources.list.d"),
        lists_dir,
        os.path.join(lists_dir, "partial"),
        archives_dir,
        os.path.join(archives_dir, "partial"),
        dpkg_dir,
    ):
        ensure_directory(path)

    status_path = os.path.join(dpkg_dir, "status")
    if not os.path.exists(status_path):
        with open(status_path, "w", encoding="utf-8"):
            pass

    sources_list_path = os.path.join(etc_apt, "sources.list")
    with open(sources_list_path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(build_repository_lines(suite, architecture)))
        stream.write("\n")

    return {
        "etc_apt": etc_apt,
        "state_dir": state_dir,
        "lists_dir": lists_dir,
        "cache_dir": cache_dir,
        "archives_dir": archives_dir,
        "status_path": status_path,
    }


def configure_apt(workspace: dict[str, str], architecture: str) -> None:
    apt_pkg.init_config()
    apt_pkg.config.set("Dir", "/")
    apt_pkg.config.set("Dir::Etc", workspace["etc_apt"])
    apt_pkg.config.set("Dir::Etc::sourcelist", "sources.list")
    apt_pkg.config.set("Dir::Etc::sourceparts", "sources.list.d")
    apt_pkg.config.set("Dir::Etc::preferencesparts", "preferences.d")
    apt_pkg.config.set("Dir::State", workspace["state_dir"])
    apt_pkg.config.set("Dir::State::lists", workspace["lists_dir"])
    apt_pkg.config.set("Dir::State::status", workspace["status_path"])
    apt_pkg.config.set("Dir::Cache", workspace["cache_dir"])
    apt_pkg.config.set("Dir::Cache::archives", workspace["archives_dir"])
    apt_pkg.config.set("Debug::NoLocking", "1")
    apt_pkg.config.set("Acquire::AllowInsecureRepositories", "1")
    apt_pkg.config.set("Acquire::AllowDowngradeToInsecureRepositories", "1")
    apt_pkg.config.set("Acquire::Languages", "none")
    apt_pkg.config.set("APT::Install-Recommends", "0")
    apt_pkg.config.set("APT::Install-Suggests", "0")
    apt_pkg.config.set("APT::Architecture", architecture)
    apt_pkg.config.clear("APT::Architectures")
    apt_pkg.config.set("APT::Architectures::", architecture)
    if os.path.isdir("/etc/apt/trusted.gpg.d"):
        apt_pkg.config.set("Dir::Etc::trustedparts", "/etc/apt/trusted.gpg.d")
    apt_pkg.init_system()


def refresh_package_lists() -> None:
    source_list = apt_pkg.SourceList()
    source_list.read_main_list()

    acquire = apt_pkg.Acquire()
    source_list.get_indexes(acquire)
    result = acquire.run()
    if result != apt_pkg.Acquire.RESULT_CONTINUE:
        raise RuntimeError(f"Repository metadata download failed with acquire result {result}")

    failed_items = []
    for item in acquire.items:
        if getattr(item, "complete", False):
            continue
        error_text = (getattr(item, "error_text", "") or "").strip()
        if not error_text:
            continue
        failed_items.append(f"{getattr(item, 'desc_uri', '<unknown>')}: {error_text}")
    if failed_items:
        failed = "\n".join(failed_items)
        raise RuntimeError(f"Repository metadata download did not complete successfully:\n{failed}")


def build_candidate_cache() -> tuple[dict[str, object], object]:
    cache = apt_pkg.Cache()
    dependency_cache = apt_pkg.DepCache(cache)
    packages = {package.name: package for package in cache.packages}
    return packages, dependency_cache


def get_candidate_version(dependency_cache, package):
    getter = getattr(dependency_cache, "get_candidate_ver", None)
    if getter is not None:
        return getter(package)

    version_list = getattr(package, "version_list", None) or []
    if version_list:
        return version_list[0]
    return None


def iter_dependency_groups(version) -> list[tuple[str, tuple[str, ...]]]:
    groups = []
    depends_list = getattr(version, "depends_list", {}) or {}
    for relation in DEPENDENCY_FIELDS:
        raw_groups = depends_list.get(relation) or []
        if not raw_groups and relation == "Pre-Depends":
            raw_groups = depends_list.get("PreDepends") or []
        for raw_group in raw_groups:
            alternatives = []
            for dependency in raw_group:
                target_package = getattr(dependency, "target_pkg", None)
                if target_package is None:
                    continue
                alternatives.append(target_package.name)
            if alternatives:
                groups.append((relation, tuple(dict.fromkeys(alternatives))))
    return groups


def build_reverse_dependency_edges(packages: dict[str, object], dependency_cache) -> dict[str, list[DependencyEdge]]:
    reverse_edges: dict[str, set[DependencyEdge]] = collections.defaultdict(set)
    for package_name, package in packages.items():
        candidate = get_candidate_version(dependency_cache, package)
        if candidate is None:
            continue
        for relation, alternatives in iter_dependency_groups(candidate):
            edge = DependencyEdge(package_name, relation, alternatives)
            for child_name in alternatives:
                reverse_edges[child_name].add(edge)

    return {
        package_name: sorted(edges, key=lambda edge: (edge.parent_name, edge.relation, edge.alternatives))
        for package_name, edges in reverse_edges.items()
    }


def find_dependency_chains(
    target_package: str,
    roots: dict[str, set[str]],
    reverse_edges: dict[str, list[DependencyEdge]],
    max_chains: int,
) -> tuple[list[tuple[list[str], list[DependencyEdge]]], bool]:
    queue = collections.deque([(target_package, [target_package], [])])
    chains: list[tuple[list[str], list[DependencyEdge]]] = []
    truncated = False

    while queue:
        current_name, backward_nodes, backward_edges = queue.popleft()

        if current_name in roots:
            chains.append((list(reversed(backward_nodes)), list(reversed(backward_edges))))
            if max_chains > 0 and len(chains) >= max_chains:
                truncated = True
                break

        for edge in reverse_edges.get(current_name, []):
            parent_name = edge.parent_name
            if parent_name in backward_nodes:
                continue
            queue.append((parent_name, backward_nodes + [parent_name], backward_edges + [edge]))

    return sorted(chains, key=lambda item: (len(item[0]), item[0])), truncated


def format_chain(nodes: list[str], edges: list[DependencyEdge]) -> list[str]:
    lines = []
    if len(nodes) == 1:
        lines.append(f"  {nodes[0]} (direct stage-package root)")
        return lines

    for index, edge in enumerate(edges):
        parent = nodes[index]
        child = nodes[index + 1]
        if len(edge.alternatives) > 1:
            alternative_text = " | ".join(edge.alternatives)
            lines.append(
                f"  {parent} --{edge.relation}--> {child} (alternatives: {alternative_text})"
            )
        else:
            lines.append(f"  {parent} --{edge.relation}--> {child}")
    return lines


def print_report(
    *,
    base_name: str,
    suite: str,
    architecture: str,
    scratch_directory: str,
    target_package: str,
    roots: dict[str, set[str]],
    packages: dict[str, object],
    chains: list[tuple[list[str], list[DependencyEdge]]],
    truncated: bool,
) -> int:
    print(f"Snap base: {base_name}")
    print(f"Ubuntu suite: {suite}")
    print(f"Architecture: {architecture}")
    print(f"Scratch APT workspace: {scratch_directory}")
    print(f"Requested package: {target_package}")
    print()

    if target_package not in packages:
        print("The requested package was not found in the downloaded Ubuntu repository metadata.")
        return 1

    if target_package in roots:
        origins = ", ".join(sorted(roots[target_package]))
        print("The requested package is listed directly in stage-packages.")
        print(f"Origin: {origins}")
        print()

    if not chains:
        print("No dependency chain from any stage-package root reaches the requested package.")
        return 1

    print(f"Found {len(chains)} dependency chain(s):")
    print()

    for index, (nodes, edges) in enumerate(chains, start=1):
        root_name = nodes[0]
        origins = ", ".join(sorted(roots[root_name]))
        print(f"[{index}] Root package: {root_name}")
        print(f"    Origin: {origins}")
        for line in format_chain(nodes, edges):
            print(line)
        print()

    if truncated:
        print("Output truncated because the maximum number of chains was reached.")

    return 0


def main() -> int:
    arguments = parse_arguments()
    snapcraft_path = resolve_snapcraft_path(arguments.snapcraft_yaml)
    data = load_snapcraft(snapcraft_path)

    base_name = data.get("base")
    if not base_name:
        raise ValueError(f"No base was found in {snapcraft_path}")

    suite = resolve_suite(str(base_name))
    roots = collect_stage_packages(data, arguments.arch)
    if not roots:
        raise RuntimeError(f"No stage-packages were found for architecture {arguments.arch}")

    scratch_directory = arguments.scratch_dir or tempfile.mkdtemp(prefix="stage-package-chains-")
    scratch_directory = os.path.abspath(scratch_directory)

    workspace = prepare_scratch_workspace(scratch_directory, suite, arguments.arch)
    configure_apt(workspace, arguments.arch)
    refresh_package_lists()

    packages, dependency_cache = build_candidate_cache()
    reverse_edges = build_reverse_dependency_edges(packages, dependency_cache)
    normalized_target = normalize_package_name(arguments.package)
    chains, truncated = find_dependency_chains(
        normalized_target,
        roots,
        reverse_edges,
        arguments.max_chains,
    )

    return print_report(
        base_name=str(base_name),
        suite=suite,
        architecture=arguments.arch,
        scratch_directory=scratch_directory,
        target_package=normalized_target,
        roots=roots,
        packages=packages,
        chains=chains,
        truncated=truncated,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError, apt_pkg.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
