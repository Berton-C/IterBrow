"""Question-first PoC: ordinary-turn context, no reasoner, executor or state store.

The LLM interprets applicability using the actual conversation and observations.
Known loop/tool boundaries only control prompt size; they confer no permission,
proof, completion status or belief revision. Existing memory tools retain lessons.
"""
import json

QUESTIONS = {
    "request": "What exactly did the user request, including agreed changes and constraints? What observable outcomes satisfy it? What am I assuming, omitting, weakening or substituting?",
    "recall": "What have we already tried, learned or left unfinished? Retrieve relevant lessons with chroma_query, episodes or search_transcript when needed; inspect current reality before relying on them. Do not invent recall.",
    "reuse": "Can existing code or tools satisfy this need? For unfamiliar work, find good GitHub/source examples, inspect useful implementation ideas and licensing, and adapt them to Iter's existing system instead of reinventing working parts.",
    "creative-choice": "Use the user's explicit creative preference. If unknown and consequential, offer faithful execution, helpful touches within the footprint, or bolder options. Do not delay necessary work for decorative choices.",
    "helpful-flair": "If helpful touches are welcome, what fits the requested footprint and makes this materially more useful, fun or interactive? Preserve every requested outcome; keep additions separable and disclose how they can be removed.",
    "explore-flair": "If bolder exploration is welcome, what ideas best express the user's intention? Offer meaningful expansions of scope, cost, dependencies, privacy or external effects before acting. Reversibility is not consent.",
    "failure-modes": "What plausible case would show this approach is wrong?",
    "recovery": "What working behavior and data must survive? Which existing saved revision would recover from failure? Use existing backup/hot-load/rollback tools; do not rewind memory to undo code or add another recovery system.",
    "bounded-reasoning": "Would a bounded question to existing NACE/MeTTa help with this choice? Use it only where available facts and rules apply. Unknown is legitimate; a native consultation is not mandatory for ordinary work.",
    "repair": "What observation would distinguish the competing explanations?",
    "fulfillment": "Before declaring completion or choosing to wait, re-read the actual request and agreed changes. For EACH requested outcome, what did I observe demonstrating it? What was omitted, weakened, substituted or only described? A progress message or planned fix is not performed work. Can the intended user do it without hidden manual help? What remains unverified or contradicts completion? Honor an explicit user hold; otherwise continue unfinished requested work.",
    "visual-use": "For visual work, use the controls and workflows as intended, inspect the rendered result and take screenshots where useful. A screenshot proves appearance, not behavior. Exercise meaningful failure cases with safe data and preserve existing behavior.",
    "nonvisual-use": "For nonvisual work, exercise the actual output or capability in its intended setting. Check the requested result, plausible failures and affected existing behavior. Distinguish live observations from mocks, old results and narration.",
    "durability": "Has the work been saved, and does the relevant reopen/restart behavior work? Can exact saved source/data revisions be located for recovery? Memory explains and locates artifacts; regeneration from a summary is not exact rollback.",
    "self-revision": "For self-repair, does the LOADED revision perform the repair, not merely the file on disk? Preserve communication, both memories, tools, heartbeat, hot-loading and rollback. Keep the known working revision and the lesson from any failure.",
    "learn": "Under what conditions is this lesson supported?",
    "flair-feedback": "What explicit feedback welcomed, rejected or removed an addition? Save context-specific preferences through existing memory. Current instructions override remembered preferences; silence is not approval and preferences do not automatically transfer between domains.",
}

WORK_CUE = (
    "When uncertain, pursue the question whose answer would most change your next action. "
    "Use the available tools to test it, then act on the result. Otherwise, continue the work. "
    "A plan or progress message is not completed work."
)


def question_context(experience, *, new_input=False, resumed=False):
    """Full vocabulary at intake; ordinary work uses one conditional cue."""
    assistant = next((m for m in reversed(experience) if m.get('role') == 'assistant'), {})
    names = {c.get('function', {}).get('name') for c in assistant.get('tool_calls', [])}
    if not new_input and not resumed and (not names or ('nop' in names and names <= {'send', 'nop'})):
        return ''
    if 'start_new_task' in names:
        keys = list(QUESTIONS)
    elif new_input or resumed:
        keys = ['request', 'recall', 'creative-choice', 'failure-modes', 'fulfillment']
    elif names == {'send'}:
        keys = ['fulfillment']
    else:
        # Actual successful/failed observations are already in experience.
        # The LLM selects the useful question; this helper does not classify
        # reasoning, add a critic turn, or interpret a tool result as fulfillment.
        keys = []
        if names & {'self_improve', 'revision_control'}:
            keys += ['self-revision', 'recovery']
        elif names & {'app_revision_control'}:
            keys += ['visual-use', 'durability']
        elif 'task_state' in names:
            for call in assistant.get('tool_calls', []):
                try:
                    args = json.loads(call.get('function', {}).get('arguments', '{}'))
                except (ValueError, TypeError):
                    continue
                if not isinstance(args, dict):
                    continue
                if args.get('phase') == 'planning':
                    keys += ['reuse', 'helpful-flair', 'explore-flair']
                elif args.get('phase') in ('verifying', 'complete'):
                    keys += ['fulfillment', 'visual-use', 'nonvisual-use', 'durability', 'flair-feedback']
    header = '\n\n## Contextual work questions\n' + WORK_CUE + '\n'
    return header + '\n'.join('- '+QUESTIONS[k] for k in dict.fromkeys(keys))
