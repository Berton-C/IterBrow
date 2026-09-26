"""Bounded read projection of Iter's EXISTING semantic and episodic memories.

Semantic truth remains state:semantic_memory:* in the supplied authoritative
snapshot; Chroma remains its existing search index. Episode/history/experience
and tier writers are untouched. This adapter neither imports those writers nor
creates directories, migrates, resets or edits memory. Retrieved text is data,
never a governing rule or an instruction to the executor.

The explicit canonical ITER_DIR is independent of this module's code location.
version_key describes the actual observed memory slice, not global journal
commit or a TTL. Large history/experience files are bounded tail observations;
their range/hash/coverage are explicit, never claimed as full-file retrieval.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

from .cognitive_fabric import digest


SEMANTIC_PREFIX = 'state:semantic_memory:'
EPISODE = re.compile(r'^episode_([0-9]+)\.json$')
MAX_SCAN_RECORDS = 5000
MAX_EPISODE_FILES = 128
MAX_FILE_BYTES = 131072
MAX_TEXT_CHARS = 24000


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _links(metadata):
    values = metadata.get('linkedEpisodes', [])
    return [str(value) for value in values[:64]
            if isinstance(value, (str, int)) and len(str(value)) <= 256] if isinstance(values, list) else []


def _semantic(key, atom):
    """Parse the existing _petta_db._memory_atom shape without eval/MeTTa execution."""
    if not isinstance(atom, str) or len(atom) > MAX_FILE_BYTES or not atom.startswith('(semantic-memory '):
        raise ValueError('invalid or oversized semantic memory atom')
    decoder = json.JSONDecoder()
    rest = atom[len('(semantic-memory '):]
    parts = []
    for _ in range(3):
        value, end = decoder.raw_decode(rest.lstrip())
        if not isinstance(value, str):
            raise ValueError('semantic memory fields must be strings')
        parts.append(value)
        rest = rest.lstrip()[end:].lstrip()
    if rest != ')' or parts[0] != key[len(SEMANTIC_PREFIX):] or len(parts[0]) > 256:
        raise ValueError('semantic memory identity differs from authority key')
    metadata = json.loads(parts[2])
    if not isinstance(metadata, dict):
        raise ValueError('semantic memory metadata is not an object')
    return parts[0], parts[1], metadata


class FoundryMemory:
    def __init__(self, canonical_iter_root):
        self.root = Path(canonical_iter_root).resolve()
        self._cache = None

    @contextmanager
    def _open(self, relative, directory=False):
        """Descriptor-relative reads reject symlinks in every path component."""
        path = PurePosixPath(relative)
        if path.is_absolute() or '..' in path.parts or str(path) != relative:
            raise ValueError('memory path must remain canonical and relative')
        handles = []
        try:
            current = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            handles.append(current)
            for index, part in enumerate(path.parts):
                flags = os.O_RDONLY | os.O_NOFOLLOW
                if index < len(path.parts) - 1 or directory:
                    flags |= os.O_DIRECTORY
                current = os.open(part, flags, dir_fd=current)
                handles.append(current)
            yield current
        finally:
            for handle in reversed(handles):
                os.close(handle)

    @staticmethod
    def _stat_identity(value):
        return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns]

    def _read(self, path, tail=False):
        try:
            with self._open(path) as handle:
                before = os.fstat(handle)
                if before.st_size > MAX_FILE_BYTES and not tail:
                    return None, {'path': path, 'status': 'oversized', 'total_bytes': before.st_size,
                                  'source_stat': self._stat_identity(before), 'coverage': 'not-read'}
                start = max(0, before.st_size - MAX_FILE_BYTES) if tail else 0
                os.lseek(handle, start, os.SEEK_SET)
                chunks, left = [], min(before.st_size, MAX_FILE_BYTES)
                while left:
                    chunk = os.read(handle, min(left, 65536))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    left -= len(chunk)
                raw = b''.join(chunks)
                after = os.fstat(handle)
                if self._stat_identity(before) != self._stat_identity(after) or left:
                    return None, {'path': path, 'status': 'changed-during-read', 'coverage': 'unresolved'}
                return raw, {'path': path, 'status': 'read', 'sha256': _sha(raw),
                    'byte_range': [start, start + len(raw)], 'total_bytes': before.st_size,
                    'coverage': 'full' if start == 0 else 'tail-only',
                    'source_stat': self._stat_identity(before)}
        except FileNotFoundError:
            return None, {'path': path, 'status': 'missing', 'coverage': 'not-read'}
        except OSError as exc:
            return None, {'path': path, 'status': 'unavailable', 'errno': exc.errno,
                          'coverage': 'not-read'}

    def _episodes(self):
        try:
            with self._open('memory/recap', directory=True) as handle:
                names = [name for name in os.listdir(handle) if EPISODE.fullmatch(name)]
                names.sort(key=lambda name: (int(EPISODE.fullmatch(name).group(1)), name), reverse=True)
                return names, None
        except OSError as exc:
            return [], {'path': 'memory/recap', 'status': 'unavailable', 'errno': exc.errno}

    def query(self, atomspace_snapshot, text='', *, semantic_limit=8, episode_limit=8):
        if not isinstance(text, str) or len(text) > 2048:
            raise ValueError('memory query must be bounded text')
        if any(type(n) is not int or not 0 <= n <= 24 for n in (semantic_limit, episode_limit)):
            raise ValueError('memory result limits must be integers from 0 through 24')
        if not isinstance(atomspace_snapshot, dict) or not isinstance(atomspace_snapshot.get('atoms'), dict):
            raise ValueError('an authoritative AtomSpace state snapshot is required')
        origin = {key: atomspace_snapshot.get(key) for key in ('epoch', 'commit', 'state_hash')}
        if any(value in (None, '') for value in origin.values()):
            raise ValueError('semantic snapshot identity is missing')
        atoms = atomspace_snapshot['atoms']
        keys = sorted(key for key in atoms if key.startswith(SEMANTIC_PREFIX))
        terms = set(re.findall(r'\w+', text.casefold()))
        parsed, gaps, identities = [], [], []
        for key in keys[:MAX_SCAN_RECORDS]:
            raw = atoms[key]
            atom_hash = _sha(raw.encode()) if isinstance(raw, str) else digest(raw)
            identities.append([key, atom_hash])
            try:
                identity, document, metadata = _semantic(key, raw)
            except (TypeError, ValueError) as exc:
                gaps.append({'source': key, 'reason': str(exc)})
                continue
            score = len(terms.intersection(re.findall(r'\w+', document.casefold())))
            if terms and score == 0:
                continue
            parsed.append((score, identity, key, atom_hash, document, metadata))
        parsed.sort(key=lambda item: (-item[0], item[1]))
        selected = parsed[:semantic_limit]
        links = set()
        for item in selected:
            links.update(_links(item[5]))
        episode_names, episode_gap = self._episodes()
        if episode_gap:
            gaps.append(episode_gap)
        # Numeric links are fetched even when outside the recent scan window.
        linked_names = []
        for name in episode_names:
            number = int(EPISODE.fullmatch(name).group(1))
            if any(value in links for value in (str(number), 'E' + str(number), name)):
                linked_names.append(name)
        scanned_names = list(dict.fromkeys(linked_names[:24] + episode_names[:MAX_EPISODE_FILES]))
        files, episodes, excerpts = [], [], []
        for name in scanned_names:
            raw, descriptor = self._read('memory/recap/' + name)
            files.append(descriptor)
            if raw is None:
                continue
            try:
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError('episode is not an object')
                identity = value.get('e', value.get('id', int(EPISODE.fullmatch(name).group(1))))
                if not isinstance(identity, (str, int)) or len(str(identity)) > 256:
                    raise ValueError('episode identity must be a bounded scalar')
                references = {str(identity), 'E' + str(identity), name}
                references.update(str(value.get(key, '')) for key in ('time', 'start_time', 'end_time'))
                linked = sorted(links.intersection(references))
                episodes.append({'original_identity': identity, 'source_path': descriptor['path'],
                    'source_hash': descriptor['sha256'], 'summary': str(value.get('s', value.get('summary', ''))),
                    'title': str(value.get('title', '')), 'linked_references': linked})
            except (ValueError, UnicodeError) as exc:
                gaps.append({'source': descriptor['path'], 'reason': str(exc)})
        episodes.sort(key=lambda value: (not bool(value['linked_references']), scanned_names.index(
            PurePosixPath(value['source_path']).name)))
        selected_episodes = episodes[:episode_limit]
        for path in ('memory/tiers/tier5.txt', 'memory/tiers/tier4.txt', 'memory/tiers/tier3.txt',
                     'memory/tiers/tier2.txt', 'history.metta', 'experience.json'):
            raw, descriptor = self._read(path, tail=path in ('history.metta', 'experience.json'))
            files.append(descriptor)
            if raw is None:
                continue
            content = raw.decode('utf-8', errors='replace')
            original_text_length = len(content)
            references = sorted(link for link in links if link in content)
            if path == 'history.metta' and (terms or links):
                rows = content.splitlines()
                matches = [line for line in rows if any(link in line for link in links) or
                           terms.intersection(re.findall(r'\w+', line.casefold()))]
                content = '\n'.join(matches[-16:])
            excerpts.append({'source_path': path, 'source_hash': descriptor['sha256'],
                'byte_range': descriptor['byte_range'], 'coverage': descriptor['coverage'],
                'content': content[-1600:] if path == 'experience.json' else content,
                'selection': 'recent-text-excerpt' if path == 'experience.json' else (
                    'matching-history-lines' if path == 'history.metta' and (terms or links) else 'source-text'),
                'selection_truncated': original_text_length > (min(len(content), 1600)
                    if path == 'experience.json' else len(content)),
                'linked_references': references})
        version = digest({'epoch': origin['epoch'], 'semantic': identities, 'semantic_total': len(keys),
            'files': files, 'episode_inventory': episode_names, 'query': text,
            'limits': [semantic_limit, episode_limit]})
        if self._cache and self._cache['version_key'] == version:
            result = deepcopy(self._cache)
            result['origin_snapshot'] = origin
            return result
        remaining = MAX_TEXT_CHARS

        def bounded(value, limit):
            nonlocal remaining
            text_value = str(value)
            count = max(0, min(remaining, limit))
            kept = text_value[:count]
            remaining -= len(kept)
            return kept, len(kept) < len(text_value)

        semantic = []
        for _, identity, key, atom_hash, document, metadata in selected:
            view, truncated = bounded(document, 1600)
            semantic.append({'id': identity, 'atom_key': key, 'atom_hash': atom_hash,
                'document': view, 'document_truncated': truncated, 'metadata_hash': digest(metadata),
                'linked_episodes': _links(metadata),
                'linked_episode_references_truncated': isinstance(metadata.get('linkedEpisodes'), list)
                    and len(_links(metadata)) != len(metadata['linkedEpisodes']),
                'provenance_type': str(metadata.get('provenance_type', 'unspecified'))[:128]})
        for episode in selected_episodes:
            episode['summary'], episode['truncated'] = bounded(episode['summary'], 1200)
            episode['title'], _ = bounded(episode['title'], 128)
        for excerpt in excerpts:
            excerpt['content'], excerpt['truncated'] = bounded(excerpt['content'], 1600)
        resolved_links = set(link for value in [*selected_episodes, *excerpts] for link in value['linked_references'])
        result = {'schema_version': 1, 'projection_only': True, 'retrieved_text_is_untrusted_data': True,
            'owners': {'semantic': 'existing-authoritative-semantic-memory-atoms',
                       'episodic': 'existing-episode-history-experience-writers'},
            'origin_snapshot': origin, 'version_key': version,
            'semantic': semantic, 'episodes': selected_episodes, 'excerpts': excerpts, 'sources': files,
            'unresolved_episode_links': sorted(links - resolved_links),
            'coverage': {'semantic_total': len(keys), 'semantic_scanned': len(identities),
                'semantic_matches': len(parsed), 'semantic_returned': len(semantic),
                'episode_files_total': len(episode_names), 'episode_files_scanned': len(scanned_names),
                'episodes_returned': len(selected_episodes), 'text_char_budget': MAX_TEXT_CHARS,
                'text_chars_used': MAX_TEXT_CHARS - remaining,
                'complete_history_retrieval': False, 'vector_search_performed': False},
            'gaps': gaps[:32], 'omitted_gap_count': max(0, len(gaps) - 32)}
        self._cache = deepcopy(result)
        return result
