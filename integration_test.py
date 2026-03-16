#!/usr/bin/env python3
"""SIEVE Integration Test — Full pipeline with realistic filter outputs.

Demonstrates the complete pipeline: extract → filter → ATHENA → digest
using real extracted content and realistic filter classifications.
"""
import sys, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, ".")

from sieve.models import (
    ExtractedContent, FilteredContent, Claim,
    ContentType, SignalClass
)
from sieve.pipeline import SievePipeline
from sieve.athena_adapter import AthenaExporter
from sieve.dedup import DeduplicationStore, jaccard_similarity, content_fingerprint


# ─── Realistic filter outputs based on actual content analysis ────────────────

MOLITOR_POST_TEXT = """Most engineering software is about to become invisible.
Over the past weeks, Vlad and I shared several posts about "Vibe Engineering".
We showed that you can generate mechanical parts in CAD tools (Onshape by PTC),
PCB layouts in electronic design environments, AUTOSAR architectures via Python,
almost fully automated using Anthropic's Claude Code.
A recurring criticism kept coming up: the generated artifacts were too simple.
And that criticism is completely fair.
The examples were under-complex and not particularly relevant for real product development.
But there is an obvious reason.
I have never designed complex CAD parts.
I have never created real PCB layouts.
And I have never built production-grade AUTOSAR architectures.
My intention was never to claim that AI can already outperform experienced engineers.
The point was much simpler:
If experts use these tools, they can dramatically accelerate their work.
So this weekend I ran a different experiment.
This time in a domain where I actually have deep experience:
Nonlinear control of machine tools in MathWorks Matlab/Simulink: the topic of my PhD for 3.5 years.
The task: Design a Simulink model for closed-loop position control of a nonlinear gearbox
(3D Servo Press from PtU - TU Darmstadt).
The Simulink model needed to include: kinematic modeling, Jacobian matrix computation,
linearization around an operating point, controller design, trajectory planning, full simulation.
But with one constraint: No clicking in Simulink. No writing Matlab code.
Instead: Claude Code connected to Simulink via MCP.
What happened next honestly surprised me!
3 prompts. 45 minutes. The model compiled. The simulation ran. Control signals were plotted.
And the system even generated a simple stick-model animation of the gearbox.
For me, this was the real aha moment. Engineering is about to change dramatically.
Engineers who know how to inject the right context into AI systems will massively outperform those who don't.
The barriers between idea and implementation are collapsing. And honestly, it's pretty mind-blowing.
How do you think AI agents will change the way engineers work with tools like CAD, Simulink or EDA?"""


def create_molitor_result() -> FilteredContent:
    """Realistic filter output for the Molitor LinkedIn post."""
    return FilteredContent(
        url="https://linkedin.com/posts/dirk-molitor/vibe-engineering-simulink",
        title="Most engineering software is about to become invisible",
        author="Dr. Dirk Alexander Molitor",
        date="2026-03",
        source_type=ContentType.LINKEDIN_POST,
        signal_class=SignalClass.MODERATE_SIGNAL,
        signal_score=0.58,
        summary=(
            "Molitor used Claude Code + MathWorks MCP server to generate a Simulink "
            "closed-loop control model for a nonlinear servo press (his PhD topic). "
            "The model compiled and simulated in 45 minutes without manual Simulink "
            "interaction. The honest admission that earlier CAD/PCB/AUTOSAR demos "
            "were under-complex (outside his expertise) is the most credible part."
        ),
        key_claims=[
            Claim(
                "Claude Code generated a working Simulink model for nonlinear position control in 45 min via 3 prompts",
                "anecdotal", "medium", verifiable=True,
            ),
            Claim(
                "The generated model included kinematics, Jacobian, linearization, controller design, trajectory planning, and simulation",
                "anecdotal", "medium", verifiable=True,
            ),
            Claim(
                "Experts using AI tools will massively outperform those who don't",
                "logical_argument", "low", verifiable=False,
            ),
            Claim(
                "Engineering tool interfaces are shifting from human-operated to agent-operated",
                "logical_argument", "medium", verifiable=False,
            ),
        ],
        novel_insights=[
            "MathWorks MCP server enables programmatic Simulink model creation from Claude Code — this is a concrete new capability, not just a concept",
            "Domain expertise + AI context injection is the real multiplier, not AI alone — demonstrated by comparing his weak CAD results vs strong Simulink results",
            "The honest comparison between in-domain (Simulink) and out-of-domain (CAD) results is itself informative about where AI-assisted engineering actually works",
        ],
        open_questions=[
            "Did the generated controller actually produce physically valid behavior, or just non-error output?",
            "What was in the 3 prompts? The prompt engineering is the real contribution but isn't shared",
            "How does this compare to an experienced engineer's 45 minutes of manual Simulink work?",
            "Would this work for a more complex multi-DOF mechanism, or only simple kinematic chains?",
        ],
        related_domains=["Simulink", "MCP", "nonlinear control", "servo press", "Claude Code", "model-based design"],
        marketing_patterns=[
            "Dramatic pacing: 'What happened next honestly surprised me!'",
            "Vague superlative: 'pretty mind-blowing'",
            "Consultant framing: 'Engineering is about to change dramatically' (Accenture employee)",
            "Engagement bait question at the end: 'How do you think AI agents will change...'",
        ],
        engagement_bait=[
            "Engagement-bait closing question targeting broad audience",
            "Staccato dramatic reveal: '3 prompts. 45 minutes. The model compiled.'",
        ],
        unsubstantiated_claims=[
            "'Barriers between idea and implementation are collapsing' — not demonstrated, only one example on a familiar problem",
            "'Massively outperform' — no comparison baseline provided",
        ],
        knowledge_nodes=[
            {
                "concept": "MathWorks MCP Server",
                "type": "tool",
                "description": "MCP server enabling Claude Code to programmatically create MATLAB files and Simulink models",
                "connections": ["Claude Code", "Simulink", "MCP", "MATLAB"],
                "source_quality": "medium",
            },
            {
                "concept": "Vibe Engineering",
                "type": "method",
                "description": "Using AI agents (Claude Code + MCP) to interact with engineering tools (CAD, Simulink, EDA) via natural language",
                "connections": ["Claude Code", "MCP", "Onshape", "Simulink", "AUTOSAR"],
                "source_quality": "medium",
            },
            {
                "concept": "Nonlinear servo press control",
                "type": "architecture",
                "description": "Closed-loop position control with kinematic modeling, Jacobian, linearization for 3D servo press from PtU Darmstadt",
                "connections": ["Simulink", "nonlinear control", "Jacobian matrix", "trajectory planning"],
                "source_quality": "medium",
            },
            {
                "concept": "Dirk Molitor",
                "type": "person",
                "description": "PhD TU Darmstadt (nonlinear control, servo presses), now Accenture industrial AI. Researched 137 papers on AI in engineering with DFKI/Fraunhofer.",
                "connections": ["Accenture", "TU Darmstadt", "Vibe Engineering", "Vlad Larichev"],
                "source_quality": "high",
            },
        ],
        connections_to_existing=["MCP", "Claude Code", "Simulink", "AUTOSAR", "Onshape"],
    )


def create_synera_result() -> FilteredContent:
    """Realistic filter for the Synera/Accenture webinar summary."""
    return FilteredContent(
        url="https://www.synera.io/news/agentic-ai-automation-trends-in-engineering",
        title="Summary Webinar with Accenture: Agentic AI & Automation Trends in Engineering",
        author=None,
        date="2026-01-18",
        source_type=ContentType.BLOG_POST,
        signal_class=SignalClass.MODERATE_SIGNAL,
        signal_score=0.62,
        summary=(
            "Webinar summary covering Molitor's research (137 papers analyzed with DFKI/Fraunhofer) "
            "on AI maturity in engineering. Distinguishes vertical AI (single-domain copilots in silos) "
            "from horizontal digital thread (connected across lifecycle). Introduces 'Software 3.0' "
            "formula: LLM + Context + Tooling = Autonomous Agent."
        ),
        key_claims=[
            Claim(
                "137 scientific publications analyzed to map AI maturity in engineering",
                "data", "high", verifiable=True,
            ),
            Claim(
                "Most current AI applications are vertical/siloed, not horizontally integrated",
                "data", "high", verifiable=True,
            ),
            Claim(
                "Context (legacy data, past decisions, standards) is the bridge between non-deterministic LLMs and deterministic engineering",
                "expert_opinion", "medium", verifiable=False,
            ),
        ],
        novel_insights=[
            "The vertical vs horizontal AI distinction in engineering is well-articulated and backed by the 137-paper survey",
            "Software 3.0 formula (LLM + Context + Tooling = Agent) is a useful mental model for engineering AI architecture",
        ],
        open_questions=[
            "Where is the full 137-paper survey published? What methodology?",
            "How do companies actually make the vertical-to-horizontal transition?",
        ],
        related_domains=["industrial AI", "digital thread", "agentic AI", "engineering workflows"],
        marketing_patterns=[
            "Synera product promotion embedded in educational webinar content",
            "Buzzword density: 'digital thread', 'Software 3.0', 'autonomous agents'",
        ],
        engagement_bait=[],
        unsubstantiated_claims=[
            "'Some industry leaders began to scale AI out of pilots into production' — which ones? no examples given",
        ],
        knowledge_nodes=[
            {
                "concept": "Vertical vs Horizontal AI in engineering",
                "type": "finding",
                "description": "Most AI in engineering is vertical (single-domain). Horizontal integration across lifecycle is the 2026 goal.",
                "connections": ["digital thread", "engineering AI", "DFKI", "Fraunhofer"],
                "source_quality": "high",
            },
            {
                "concept": "Software 3.0 formula",
                "type": "method",
                "description": "LLM + Context + Tooling = Autonomous AI Agent. Context = legacy data, past decisions, standards.",
                "connections": ["agentic AI", "LLM", "engineering context"],
                "source_quality": "medium",
            },
        ],
        connections_to_existing=["Dirk Molitor", "Accenture", "DFKI", "Fraunhofer"],
    )


def create_cockcroft_result() -> FilteredContent:
    """Realistic filter for Adrian Cockcroft's claude-flow post."""
    return FilteredContent(
        url="https://adrianco.medium.com/vibe-coding-is-so-last-month-my-first-agent-swarm-experience-with-claude-flow-414b0bd6f2f2",
        title="Vibe Coding is so Last Month — My First Agent Swarm Experience with claude-flow",
        author="Adrian Cockcroft",
        date="2025-06-27",
        source_type=ContentType.MEDIUM_ARTICLE,
        signal_class=SignalClass.HIGH_SIGNAL,
        signal_score=0.78,
        summary=(
            "Cockcroft (ex-Netflix VP, AWS VP) documents his hands-on experience with claude-flow, "
            "a multi-agent orchestrator for Claude Code. Spawned 5 parallel agents that coordinated "
            "via shared memory to implement a 'house consciousness' IoT system. Provides concrete "
            "details: agent names, task types, token counts (74.3k), timing (3m 32s), and the "
            "actual coordination patterns. Hit quota limits mid-session."
        ),
        key_claims=[
            Claim(
                "claude-flow spawns parallel Claude Code agents that coordinate via shared memory",
                "anecdotal", "high", verifiable=True,
            ),
            Claim(
                "5 parallel agents completed implementation tasks with automatic coordination",
                "anecdotal", "high", verifiable=True,
            ),
            Claim(
                "Individual agent task: 15 tool uses, 74.3k tokens, 3m 32.7s",
                "data", "high", verifiable=True,
            ),
        ],
        novel_insights=[
            "Multi-agent swarms for code generation are now practical, not theoretical — with concrete metrics",
            "Agent coordination via shared memory/todos is an emergent architecture pattern",
            "Quota exhaustion as a real constraint on multi-agent workflows — practical limitation rarely discussed",
        ],
        open_questions=[
            "What's the code quality of swarm-generated output vs single-agent?",
            "How do you debug when 5 agents made changes simultaneously?",
            "Does the coordination overhead negate the parallelism benefit?",
        ],
        related_domains=["multi-agent systems", "Claude Code", "claude-flow", "IoT", "agentic coding"],
        marketing_patterns=[],
        engagement_bait=[
            "Title: 'Vibe Coding is so Last Month' — provocative but earned by the content depth",
        ],
        unsubstantiated_claims=[],
        knowledge_nodes=[
            {
                "concept": "claude-flow",
                "type": "tool",
                "description": "Multi-agent orchestrator for Claude Code. Spawns parallel agents with shared memory coordination.",
                "connections": ["Claude Code", "multi-agent", "parallel execution"],
                "source_quality": "high",
            },
            {
                "concept": "Agent swarm coordination via shared memory",
                "type": "architecture",
                "description": "Agents use shared todos and memory keys for coordination. Automatic task distribution.",
                "connections": ["claude-flow", "multi-agent", "distributed systems"],
                "source_quality": "high",
            },
            {
                "concept": "Adrian Cockcroft",
                "type": "person",
                "description": "Ex-Netflix VP (cloud architecture), ex-AWS VP. Now exploring multi-agent development.",
                "connections": ["Netflix", "AWS", "cloud architecture", "claude-flow"],
                "source_quality": "high",
            },
        ],
        connections_to_existing=["Claude Code", "multi-agent systems", "MCP"],
    )


def create_cao_result() -> FilteredContent:
    """Realistic filter for the Vibe Coding leadership report."""
    return FilteredContent(
        url="https://dev.to/yong_cao_c38d8c5787fc4a45/the-first-evolution-of-vibe-coding-engineering-leadership-report-469d",
        title="The First Evolution of Vibe Coding: Engineering Leadership Report",
        author="Yong Cao",
        date="2026-03-12",
        source_type=ContentType.BLOG_POST,
        signal_class=SignalClass.MODERATE_SIGNAL,
        signal_score=0.55,
        summary=(
            "Synthesizes empirical data on AI code generation failures: 31.7% of AI-generated "
            "projects fail to execute out-of-box, iterative AI improvements cause 37.6% spike "
            "in critical security vulnerabilities after 5 rounds. Cites University of Naples "
            "research on AI code defect profiles. Proposes 'SpecMind Framework' and strict "
            "human-in-the-loop policies."
        ),
        key_claims=[
            Claim(
                "31.7% of AI-generated projects fail to execute out-of-the-box",
                "data", "medium", verifiable=True,
            ),
            Claim(
                "37.6% spike in critical security vulnerabilities after 5 iterative AI rounds",
                "data", "medium", verifiable=True,
            ),
            Claim(
                "Code bugs (52.6%) outweigh dependency errors (10.5%) as primary failure cause",
                "data", "medium", verifiable=True,
            ),
            Claim(
                "No more than 3 consecutive AI-only iterations permitted on any code block",
                "expert_opinion", "low", verifiable=False,
            ),
        ],
        novel_insights=[
            "Quantified failure rates for AI-generated code execution (31.7%) with source",
            "Iterative AI refinement degrades security — counterintuitive finding",
            "AI code has lower lexical diversity than human code (template-like patterns)",
        ],
        open_questions=[
            "What's the sample size and methodology behind the 31.7% figure?",
            "Does the 37.6% security vulnerability increase hold across languages?",
            "Is the SpecMind Framework actually tested or just proposed?",
        ],
        related_domains=["code quality", "AI security", "vibe coding", "engineering leadership"],
        marketing_patterns=[
            "Self-styled 'Chief Technology Risk Officer' framing adds false authority",
            "SpecMind Framework appears to be the author's proposal, not an established methodology",
        ],
        engagement_bait=[],
        unsubstantiated_claims=[
            "The specific percentages (31.7%, 37.6%, 52.6%) need source verification — citations are vague",
        ],
        knowledge_nodes=[
            {
                "concept": "AI code execution failure rate",
                "type": "finding",
                "description": "31.7% of AI-generated projects fail to execute. 52.6% of failures are code bugs, 10.5% dependency errors.",
                "connections": ["vibe coding", "code quality", "AI code generation"],
                "source_quality": "medium",
            },
            {
                "concept": "AI iterative security degradation",
                "type": "finding",
                "description": "37.6% spike in critical security vulnerabilities after 5 rounds of iterative AI improvement.",
                "connections": ["AI security", "code quality", "iterative development"],
                "source_quality": "medium",
            },
        ],
        connections_to_existing=["Claude Code", "vibe coding", "code quality"],
    )


def run_integration_test():
    """Run the full pipeline integration test."""
    print("=" * 70)
    print("SIEVE Integration Test — Full Pipeline")
    print("=" * 70)

    # Create pipeline with dedup
    pipe = SievePipeline(
        output_dir="./sieve_output",
        dedup=True,
    )

    # Feed in realistic filter results
    results = [
        create_molitor_result(),
        create_synera_result(),
        create_cockcroft_result(),
        create_cao_result(),
    ]

    for r in results:
        pipe.results.append(r)
        pipe.athena.ingest(r)

        # Register in dedup
        if pipe._dedup:
            pipe._dedup.register(
                text=f"{r.title} {r.summary}",
                url=r.url,
                title=r.title,
                author=r.author,
            )

    # ─── Test dedup ──────────────────────────────────────────────────
    print("\n--- Deduplication Test ---")
    dup = pipe._dedup.is_duplicate(MOLITOR_POST_TEXT, threshold=0.3)
    if dup:
        print(f"  Molitor post detected as near-duplicate of: {dup.get('title')}")
    else:
        print("  Molitor post: no duplicate found (threshold may be too high for summary vs full text)")

    # Cross-check similarity between the two Molitor-related pieces
    sim = jaccard_similarity(
        "Vibe Engineering Claude Code Simulink MCP engineering tools",
        "Vibe Engineering Claude Code Onshape CAD Simulink MCP tools"
    )
    print(f"  Topic overlap (Molitor vs Synera): {sim:.3f}")
    print(f"  Dedup store: {pipe._dedup.stats()}")

    # ─── ATHENA export ───────────────────────────────────────────────
    print("\n--- ATHENA Knowledge Graph ---")
    stats = pipe.athena.stats()
    print(f"  Total nodes: {stats['total_nodes']}")
    print(f"  Total edges: {stats['total_edges']}")
    print(f"  By type: {stats['nodes_by_type']}")
    print(f"  By quality: {stats['nodes_by_quality']}")

    print("\n  Sample nodes:")
    for nid, node in list(pipe.athena.nodes.items())[:6]:
        conns = ", ".join(node.connections[:3])
        if len(node.connections) > 3:
            conns += f" +{len(node.connections)-3} more"
        print(f"    [{node.node_type:12s}] {node.concept}")
        print(f"                  quality={node.source_quality:.2f} -> {conns}")

    # ─── Save everything ─────────────────────────────────────────────
    print("\n--- Saving Results ---")
    json_path, md_path, athena_path = pipe.save_results(prefix="integration_test")

    # ─── Print digest ────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("MARKDOWN DIGEST")
    print("=" * 70)
    digest = pipe.generate_digest()
    # Windows cp1252 console can't print Unicode — encode safely
    import sys
    sys.stdout.buffer.write(digest.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")

    return pipe


if __name__ == "__main__":
    pipe = run_integration_test()
