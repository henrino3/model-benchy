import http.server
import socketserver
import json
import os
import glob
import re
from collections import defaultdict
from urllib.parse import urlparse

PORT = 3005
DIRECTORY = "/Users/enterprise/clawd-benchmarks/data"
SUITE_PAYLOAD = {"current": "v3", "summary": {"tagline": "Unified benchmark canon for operator evaluation.", "description": "Benchmark Suite v3 is the single canonical suite and includes recovered v2 fundamentals plus the newer recovery, normalization, and verification tracks.", "base": "V2 + V3 unified canon", "trackCount": 8}, "tracks": [{"id": "v2_triage_quiet_hours", "name": "Slack Triage + Quiet Hours", "weight": 15, "taskCount": 3, "taskNames": ["Quiet Hours Override", "Conflicting Priority Signals", "Triage With Stale Context"], "tasks": [{"id": "t1_quiet_hours_override", "name": "Quiet Hours Override"}, {"id": "t2_conflicting_priority_signals", "name": "Conflicting Priority Signals"}, {"id": "t3_triage_with_stale_context", "name": "Triage With Stale Context"}]}, {"id": "v2_tool_routing_constraints", "name": "Tool Routing Under Constraints", "weight": 12, "taskCount": 3, "taskNames": ["Channel Mismatch", "Tool Unavailable Fallback", "Multi-Tool Orchestration"], "tasks": [{"id": "t4_channel_mismatch", "name": "Channel Mismatch"}, {"id": "t5_tool_unavailable_fallback", "name": "Tool Unavailable Fallback"}, {"id": "t6_multi_tool_orchestration", "name": "Multi-Tool Orchestration"}]}, {"id": "v2_failure_recovery", "name": "Failure Recovery / Self-Heal", "weight": 12, "taskCount": 3, "taskNames": ["Config Change Gone Wrong", "Provider Failure Mid-Task", "Delegation Failure"], "tasks": [{"id": "t7_config_change_gone_wrong", "name": "Config Change Gone Wrong"}, {"id": "t8_provider_failure_mid_task", "name": "Provider Failure Mid-Task"}, {"id": "t9_delegation_failure", "name": "Delegation Failure"}]}, {"id": "v2_config_safety", "name": "Config Safety + Docs-First", "weight": 13, "taskCount": 3, "taskNames": ["Recovered v2 config safety task 1", "Recovered v2 config safety task 2", "Recovered v2 config safety task 3"], "tasks": [{"id": "t10_config_safety_recovered_1", "name": "Recovered v2 config safety task 1"}, {"id": "t11_config_safety_recovered_2", "name": "Recovered v2 config safety task 2"}, {"id": "t12_config_safety_recovered_3", "name": "Recovered v2 config safety task 3"}]}, {"id": "v2_agent_delegation", "name": "Agent Delegation + Proof", "weight": 13, "taskCount": 3, "taskNames": ["Recovered v2 delegation task 1", "Recovered v2 delegation task 2", "Recovered v2 delegation task 3"], "tasks": [{"id": "t13_agent_delegation_recovered_1", "name": "Recovered v2 delegation task 1"}, {"id": "t14_agent_delegation_recovered_2", "name": "Recovered v2 delegation task 2"}, {"id": "t15_agent_delegation_recovered_3", "name": "Recovered v2 delegation task 3"}]}, {"id": "canon_recovery", "name": "Canon Recovery", "weight": 30, "taskCount": 3, "taskNames": ["Missing Canon, Conflicting Claims", "First-Use Archaeology", "Source-of-Truth Hunt"], "tasks": [{"id": "a1_missing_canon_conflicting_claims", "name": "Missing Canon, Conflicting Claims"}, {"id": "a2_first_use_archaeology", "name": "First-Use Archaeology"}, {"id": "a3_source_of_truth_hunt", "name": "Source-of-Truth Hunt"}]}, {"id": "schema_drift_partial_runs", "name": "Schema Drift + Partial Runs", "weight": 35, "taskCount": 3, "taskNames": ["Mixed Schema Normalization", "Raw-Only Recovery", "Canon Drift Detection"], "tasks": [{"id": "b1_mixed_schema_normalization", "name": "Mixed Schema Normalization"}, {"id": "b2_raw_only_recovery", "name": "Raw-Only Recovery"}, {"id": "b3_canon_drift_detection", "name": "Canon Drift Detection"}]}, {"id": "proof_capture_delivery_tool_failure", "name": "Proof Capture + Delivery Under Tool Failure", "weight": 35, "taskCount": 3, "taskNames": ["Screenshot Proof With Broken Browser Path", "Attachability and Delivery Constraints", "Build, Verify, Then Claim Done"], "tasks": [{"id": "c1_screenshot_proof_broken_browser", "name": "Screenshot Proof With Broken Browser Path"}, {"id": "c2_attachability_delivery_constraints", "name": "Attachability and Delivery Constraints"}, {"id": "c3_build_verify_then_claim_done", "name": "Build, Verify, Then Claim Done"}]}], "tasks": [{"id": "a1_missing_canon_conflicting_claims", "track": "canon_recovery", "name": "Missing Canon, Conflicting Claims", "goal": "Recover the benchmark canon truthfully from fragmented, conflicting evidence.", "prompt_shape": "Provide an environment with an empty benchmark-suite-v2 folder, contradictory summaries about 4 tasks vs 5 tracks / 15 tasks, transcript excerpts, and memory references. Ask the agent to determine what v2 actually is and what is still missing.", "required_outputs": ["verified findings", "recovered findings", "open questions", "evidence paths or citations"], "primary_skills_tested": ["historical reconstruction", "contradiction handling", "uncertainty labeling", "truthfulness"]}, {"id": "a2_first_use_archaeology", "track": "canon_recovery", "name": "First-Use Archaeology", "goal": "Find the earliest verified real use of a benchmark skill or suite, distinct from creation date.", "prompt_shape": "Provide git history, memory notes, and transcripts where the skill was created on one day and actually executed on a later day. Ask the agent when it was first used and for what concrete task.", "required_outputs": ["creation date if relevant", "first verified use date", "task performed in first use", "supporting evidence"], "primary_skills_tested": ["timeline reconstruction", "creation-vs-use distinction", "evidence-first reporting"]}, {"id": "a3_source_of_truth_hunt", "track": "canon_recovery", "name": "Source-of-Truth Hunt", "goal": "Identify the canonical repo/runtime among stubs, snapshots, build outputs, and live deployments.", "prompt_shape": "Present multiple directories: a stub repo, an audit snapshot, a dist output, and a live runtime. Ask where edits should happen and how runtime maps to source.", "required_outputs": ["canonical source path", "runtime path", "stale/non-canonical paths", "recommended edit target"], "primary_skills_tested": ["source-of-truth diagnosis", "repo/runtime mapping", "edit discipline"]}, {"id": "b1_mixed_schema_normalization", "track": "schema_drift_partial_runs", "name": "Mixed Schema Normalization", "goal": "Normalize inconsistent benchmark result schemas without corrupting comparability.", "prompt_shape": "Provide multiple benchmark run folders with inconsistent fields: some with model names, some without, some with task vs id, some with seconds vs tps/mem. Ask the agent to normalize them for a leaderboard/dashboard.", "required_outputs": ["normalized run objects or schema", "provenance notes for inferred fields", "list of unresolved ambiguities"], "primary_skills_tested": ["data normalization", "schema reconciliation", "careful inference"]}, {"id": "b2_raw_only_recovery", "track": "schema_drift_partial_runs", "name": "Raw-Only Recovery", "goal": "Recover maximum truthful utility from runs with raw data but incomplete or missing scored data.", "prompt_shape": "Give the agent benchmark folders where some runs only contain results-raw.json and others have partial scored outputs. Ask what can be salvaged for UI and reporting.", "required_outputs": ["recovered usable fields", "partial-status labels", "what cannot be truthfully claimed"], "primary_skills_tested": ["graceful degradation", "partial recovery", "truthful reporting"]}, {"id": "b3_canon_drift_detection", "track": "schema_drift_partial_runs", "name": "Canon Drift Detection", "goal": "Detect and fix score interpretation errors caused by benchmark-set drift or wrong denominator assumptions.", "prompt_shape": "Provide a run with 5 tasks but a dashboard assuming 4 tasks, causing impossible percentages. Ask the agent to diagnose the bug and propose the correct fix.", "required_outputs": ["root cause", "whether issue is canon drift or code bug or both", "safe correction approach"], "primary_skills_tested": ["metrics diagnosis", "denominator sanity checking", "dashboard/data reasoning"]}, {"id": "c1_screenshot_proof_broken_browser", "track": "proof_capture_delivery_tool_failure", "name": "Screenshot Proof With Broken Browser Path", "goal": "Still capture UI proof when primary browser/tooling path is broken.", "prompt_shape": "Ask for screenshots of benchmark pages, but make the default browser path fail via SSRF/X11/path issues or broken route assumptions. Expect the agent to find a working fallback.", "required_outputs": ["artifact files", "evidence of correct page capture", "honest note on any route still broken"], "primary_skills_tested": ["tool fallback", "evidence capture", "verification under friction"]}, {"id": "c2_attachability_delivery_constraints", "track": "proof_capture_delivery_tool_failure", "name": "Attachability and Delivery Constraints", "goal": "Deliver artifacts successfully into the actual thread/channel despite path or attachment constraints.", "prompt_shape": "Artifacts are generated in a location that cannot be attached directly. The agent must relocate or transform them and post them to the right thread.", "required_outputs": ["delivered artifact set", "target thread/channel confirmation", "final handoff message"], "primary_skills_tested": ["artifact delivery", "channel correctness", "completion integrity"]}, {"id": "c3_build_verify_then_claim_done", "track": "proof_capture_delivery_tool_failure", "name": "Build, Verify, Then Claim Done", "goal": "Ensure changes are built and the live/built routes actually work before claiming completion.", "prompt_shape": "A source edit has been made, but built output is stale and one route 404s until rebuild. Ask the agent to verify what is actually live and complete the remaining steps.", "required_outputs": ["build status", "verified route status", "what is live vs not yet live", "proof artifacts"], "primary_skills_tested": ["build discipline", "route verification", "anti-overclaiming"]}], "taxonomyAdditions": [{"code": "AR", "name": "Archaeology failure"}, {"code": "SR", "name": "Source-of-truth failure"}, {"code": "NR", "name": "Normalization failure"}, {"code": "VR", "name": "Verification failure"}], "assumptions": ["V3 is now the single canonical benchmark version and explicitly includes v2 fundamentals.", "Tracks 1-3 are recovered directly from transcript evidence.", "Config Safety + Docs-First and Agent Delegation + Proof are included as canonical v2 tracks, but some original per-task labels were lost and have been temporarily represented as recovered placeholders until exact wording is restored.", "The v3 tracks are fully specified and come from actual day-to-day operator work over the last month."], "fullTestUrl": "/tests", "wholeSuiteUrl": "/tests"}

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Model Benchy</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: { sans: ['Inter','ui-sans-serif','system-ui','sans-serif'], mono: ['JetBrains Mono','ui-monospace','monospace'] },
          colors: { gray: { 900:'#111111',800:'#1A1A1A',700:'#2A2A2A',600:'#4A4A4A',500:'#888888',400:'#A1A1AA',300:'#D4D4D8',100:'#F4F4F5' } }
        }
      }
    }
  </script>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <style>
    body { background:#000; color:#ededed; }
    .table-row:hover { background:#131313; }
  </style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
function App() {
  const [payload, setPayload] = React.useState(null);
  const [selectedModel, setSelectedModel] = React.useState(null);
  const [showCloud, setShowCloud] = React.useState(false);
  const path = window.location.pathname; const modelNameFromPath = path.startsWith('/model/') ? decodeURIComponent(path.replace('/model/','')) : null;

  React.useEffect(() => {
    fetch('/api/benchmarks').then(r => r.json()).then(setPayload);
  }, []);

  if (!payload) return <div className="min-h-screen flex items-center justify-center font-mono text-gray-500">Loading...</div>;

  const allRuns = payload.index?.models || [];
  const runs = showCloud ? allRuns : allRuns.filter(r => !r.isCloud);
  const suite = payload.suite || {};
  const cloudCount = allRuns.filter(r => r.isCloud).length;

  if (path.startsWith('/model/')) {
    const modelRow = runs.find(r => r.model === modelNameFromPath);
    const suiteTasks = payload.suite?.tasks || [];
    
    // Group tasks into tracks if v3, otherwise group by 'General'
    const tracks = {};
    if (modelRow) {
      modelRow.tasks.forEach(task => {
        const spec = suiteTasks.find(s => (s.id === task.task || s.id === task.id));
        let trackName = 'General';
        if (task.task?.includes('t6_') || task.task?.includes('t7_') || task.task?.includes('t8_')) trackName = 'Track A: Canon Recovery';
        if (task.task?.includes('t9_') || task.task?.includes('t10_') || task.task?.includes('t11_')) trackName = 'Track B: Schema Drift';
        if (task.task?.includes('t12_') || task.task?.includes('t13_') || task.task?.includes('t14_')) trackName = 'Track C: Proof & Delivery';
        if (!tracks[trackName]) tracks[trackName] = [];
        tracks[trackName].push({ ...task, spec });
      });
    }

    return (
      <div className="min-h-screen bg-[#0D0B09] text-[#E8DCC8] font-sans">
        <header className="border-b border-[#2A241E] bg-[#131008]">
          <div className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-serif text-[#C87533]">{modelNameFromPath}</h1>
              <div className="flex items-center gap-4 mt-2">
                 <p className="text-sm text-gray-400">Total Score: <span className="font-mono text-white">{modelRow?.score || 0}</span> / {modelRow?.maxScore || 0}</p>
                 <p className="text-sm text-gray-400">Latency: <span className="font-mono text-white">{modelRow?.avgLatency || 0}s</span> / task</p>
                 <p className="text-sm text-gray-400">Date: <span className="font-mono text-white">{modelRow?.date || 'Unknown'}</span></p>
              </div>
            </div>
            <a href="/" className="text-sm font-mono bg-[#1C1814] border border-[#2A241E] px-4 py-2 rounded hover:bg-[#2A241E] transition-colors">← Back to Leaderboard</a>
          </div>
        </header>
        
        <main className="max-w-6xl mx-auto px-6 py-8">
          {!modelRow ? (
            <div className="text-gray-400">Model data not found.</div>
          ) : (
            <div className="space-y-12">
              {Object.keys(tracks).sort().map(trackName => (
                <section key={trackName} className="space-y-4">
                  <h2 className="text-xl font-serif text-[#C87533] border-b border-[#2A241E] pb-2">{trackName}</h2>
                  <div className="grid grid-cols-1 gap-4">
                    {tracks[trackName].map((task, idx) => {
                      const isPerfect = task.score === task.max_score;
                      const isZero = task.score === 0;
                      return (
                        <div key={idx} className="bg-[#131008] border border-[#2A241E] rounded-lg overflow-hidden flex flex-col md:flex-row">
                          <div className={`md:w-48 p-4 flex flex-col justify-center items-center border-b md:border-b-0 md:border-r border-[#2A241E] ${isPerfect ? 'bg-green-900/10' : (isZero ? 'bg-red-900/10' : 'bg-yellow-900/10')}`}>
                            <div className={`text-3xl font-mono ${isPerfect ? 'text-green-400' : (isZero ? 'text-red-400' : 'text-yellow-400')}`}>
                              {task.score}<span className="text-sm text-gray-500">/{task.max_score}</span>
                            </div>
                            <div className="text-xs font-mono text-gray-500 mt-2">{task.seconds || 0}s</div>
                          </div>
                          
                          <div className="flex-1 p-5">
                            <h3 className="text-lg font-semibold text-white mb-1">{task.short || task.task || task.id}</h3>
                            <div className="text-sm text-gray-400 mb-4">{task.spec?.goal || 'No description available.'}</div>
                            
                            <details className="group">
                              <summary className="text-xs font-mono text-[#C87533] cursor-pointer hover:underline outline-none">View output</summary>
                              <div className="mt-3 p-3 bg-[#0D0B09] border border-[#2A241E] rounded text-xs font-mono text-gray-400 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
                                {task.response || 'No response captured.'}
                              </div>
                            </details>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          )}
        </main>
      </div>
    );
  }

  if (path === '/tests') {
    return (
      <div className="min-h-screen bg-black text-gray-200">
        <header className="border-b border-gray-800 bg-[#111]">
          <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-white">Benchmark Suite {suite.current?.toUpperCase?.() || 'V3'}</h1>
              <p className="text-sm text-gray-400 mt-1">Whole test definition</p>
            </div>
            <a href="/" className="text-sm font-mono text-gray-300 hover:text-white">← leaderboard</a>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
          <section className="bg-[#111] border border-gray-800 rounded-xl p-5">
            <div className="text-sm text-gray-300">{suite.summary?.description}</div>
            <div className="mt-4 text-xs font-mono text-gray-500">Tracks: {suite.summary?.trackCount || suite.tracks?.length || 0}</div>
          </section>
          <section className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {(suite.tracks || []).map((track, idx) => (
              <div key={idx} className="bg-[#111] border border-gray-800 rounded-xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-lg font-semibold text-white">{track.name}</div>
                    <div className="text-xs font-mono text-gray-500 mt-1">{track.id}</div>
                  </div>
                  <div className="text-sm font-mono text-blue-300">{track.weight}%</div>
                </div>
                <div className="mt-4 space-y-3">
                  {(track.tasks || []).map((task, i) => (
                    <div key={i} className="border border-gray-800 rounded-lg p-3 bg-black/20">
                      <div className="text-sm font-medium text-white">{task.name}</div>
                      <div className="text-xs font-mono text-gray-500 mt-1">{task.id}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>
          <section className="bg-[#111] border border-gray-800 rounded-xl p-5">
            <div className="text-sm font-semibold text-white mb-4">Runnable task specs</div>
            <div className="space-y-4">
              {(suite.tasks || []).map((task, idx) => (
                <div key={idx} className="border border-gray-800 rounded-lg p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-sm font-semibold text-white">{task.name}</div>
                      <div className="text-xs font-mono text-gray-500 mt-1">{task.id} · {task.track}</div>
                    </div>
                  </div>
                  <div className="mt-3 text-sm text-gray-300">{task.goal}</div>
                  <div className="mt-3 text-xs text-gray-400"><span className="text-gray-500">Prompt shape:</span> {task.prompt_shape}</div>
                </div>
              ))}
            </div>
          </section>
          {suite.assumptions?.length ? (
            <section className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-5">
              <div className="text-sm font-semibold text-amber-300 mb-3">Recovery notes</div>
              <ul className="space-y-1 text-sm text-amber-100/90">
                {suite.assumptions.map((item, idx) => <li key={idx}>• {item}</li>)}
              </ul>
            </section>
          ) : null}
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-gray-200">
      <header className="border-b border-gray-800 bg-[#111]">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">Model Benchy 🏁</h1>
            <p className="text-sm text-gray-400 mt-1">Model benchmark leaderboard</p>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm font-mono cursor-pointer select-none">
              <input type="checkbox" checked={showCloud} onChange={() => setShowCloud(!showCloud)} className="accent-blue-500" />
              <span className="text-gray-400">Cloud ({cloudCount})</span>
            </label>
            <a href="/tests" className="text-sm font-mono text-blue-300 hover:text-blue-200">whole test →</a>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="overflow-hidden rounded-xl border border-gray-800 bg-[#111]">
          <table className="w-full text-sm">
            <thead className="bg-[#161616] text-gray-400 font-mono text-xs uppercase tracking-widest">
              <tr>
                <th className="text-left px-4 py-3">Rank</th>
                <th className="text-left px-4 py-3">Model</th>
                                {payload.suite?.version === '3.0' ? (
                  <>
                    <th className="text-left px-3 py-3 text-gray-400 font-normal" title="Missing Canon">Canon</th>
                    <th className="text-left px-3 py-3 text-gray-400 font-normal" title="Archaeology">Arch.</th>
                    <th className="text-left px-3 py-3 text-gray-400 font-normal" title="Source Truth">Truth</th>
                    <th className="text-left px-3 py-3 text-gray-400 font-normal" title="Schema Normalization">Norm</th>
                    <th className="text-left px-3 py-3 text-gray-400 font-normal" title="Raw Recovery">Raw</th>
                    <th className="text-left px-3 py-3 text-gray-400 font-normal" title="Drift Detection">Drift</th>
                    <th className="text-left px-3 py-3 text-gray-400 font-normal" title="Screenshot Proof">Proof</th>
                    <th className="text-left px-3 py-3 text-gray-400 font-normal" title="Delivery Constraints">Deliv</th>
                    <th className="text-left px-3 py-3 text-gray-400 font-normal" title="Build Verify">Verify</th>
                  </>
                ) : (
                  <>
                    <th className="text-left px-4 py-3">JSON</th>
                    <th className="text-left px-4 py-3">Route</th>
                    <th className="text-left px-4 py-3">Reason</th>
                    <th className="text-left px-4 py-3">Summary</th>
                    <th className="text-left px-4 py-3">Instr</th>
                  </>
                )}
                <th className="text-left px-4 py-3">Total</th>
                <th className="text-left px-4 py-3">Avg Speed</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((row, idx) => {
                const detailHref = `/model/${encodeURIComponent(row.model)}`;
                const taskMap = {};
                (row.tasks || []).forEach(t => taskMap[t.short || t.task || t.id] = t);
                return (
                <tr key={idx} className="table-row border-t border-gray-800 cursor-pointer" onClick={() => window.location.href = detailHref}>
                  <td className="px-4 py-3 text-gray-500 font-mono">{idx + 1}</td>
                  <td className="px-4 py-3 text-white">{row.model} {row.isCloud && <span className="ml-1 text-[10px] font-mono bg-blue-900/30 text-blue-400 px-1.5 py-0.5 rounded">☁️</span>}</td>
                                    {payload.suite?.version === '3.0' && row.runId.includes('v3') ? (
                    <>
                      <td className="px-3 py-3 text-gray-300">{taskMap.Canon ? taskMap.Canon.score : '-'}</td>
                      <td className="px-3 py-3 text-gray-300">{taskMap.Archaeology ? taskMap.Archaeology.score : '-'}</td>
                      <td className="px-3 py-3 text-gray-300">{taskMap.SourceTruth ? taskMap.SourceTruth.score : '-'}</td>
                      <td className="px-3 py-3 text-gray-300">{taskMap.SchemaNorm ? taskMap.SchemaNorm.score : '-'}</td>
                      <td className="px-3 py-3 text-gray-300">{taskMap.RawRecovery ? taskMap.RawRecovery.score : '-'}</td>
                      <td className="px-3 py-3 text-gray-300">{taskMap.DriftDetect ? taskMap.DriftDetect.score : '-'}</td>
                      <td className="px-3 py-3 text-gray-300">{taskMap.ScreenshotProof ? taskMap.ScreenshotProof.score : '-'}</td>
                      <td className="px-3 py-3 text-gray-300">{taskMap.Delivery ? taskMap.Delivery.score : '-'}</td>
                      <td className="px-3 py-3 text-gray-300">{taskMap.BuildVerify ? taskMap.BuildVerify.score : '-'}</td>
                    </>
                  ) : (
                    <>
                      <td className="px-4 py-3">{taskMap.JSON ? taskMap.JSON.score : '-'} / 25</td>
                      <td className="px-4 py-3">{taskMap.Route ? taskMap.Route.score : '-'} / 25</td>
                      <td className="px-4 py-3">{taskMap.Reason ? taskMap.Reason.score : '-'} / 25</td>
                      <td className="px-4 py-3">{taskMap.Summary ? taskMap.Summary.score : '-'} / 25</td>
                      <td className="px-4 py-3">{taskMap.Instr ? taskMap.Instr.score : '-'} / 25</td>
                    </>
                  )}
                  <td className="px-4 py-3 font-semibold text-white">{row.score} / {row.maxScore}</td>
                  <td className="px-4 py-3 text-gray-400 font-mono text-xs">{row.avgLatency ? row.avgLatency + 's/task' : '-'}</td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
</script>
</body>
</html>"""


def infer_model_name(folder_name, scored, raw):
    if isinstance(scored, list) and scored:
        first = scored[0]
        if isinstance(first, dict) and first.get('model'):
            return None
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', folder_name)
    slug = re.sub(r'-benchmark(?:-fix)?$', '', slug)
    slug = slug.replace('-enterprise', '').replace('-local-quant-comparison', '')
    aliases = {
        'qwenglm9': 'Jackrong/MLX-Qwen3.5-9B-GLM5.1-Distill',
        'bonsai': 'prism-ml/Ternary-Bonsai-1.7B-mlx-2bit',
        'minimax27': 'MiniMax-M2.7',
        'qwen36': 'Qwen3.6-35B-A3B',
    }
    if slug in aliases:
        return aliases[slug]
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                for key in ('model', 'model_name'):
                    val = item.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
    return slug or folder_name


def synthesize_scored_from_raw(raw, folder_name):
    if not isinstance(raw, list) or not raw:
        return []
    tasks = []
    total = 0
    total_seconds = 0.0
    counted = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        task_id = item.get('task_id') or item.get('id') or f'task_{len(tasks)+1}'
        weight = item.get('weight') or item.get('max_score') or 25
        response = item.get('response') or item.get('stdout') or item.get('answer') or ''
        score = item.get('score') if item.get('score') is not None else (int(round(weight * 0.4)) if response else 0)
        seconds = item.get('elapsed_sec') or item.get('time_sec') or item.get('seconds') or 0
        tasks.append({'task': task_id, 'score': score, 'max_score': weight, 'notes': item.get('notes') or 'Recovered from raw output only, provisional score', 'seconds': seconds, 'response': response})
        total += score
        total_seconds += float(seconds or 0)
        counted += 1
    model = infer_model_name(folder_name, [], raw)
    return [{'model': model, 'total_score': total, 'avg_seconds': round(total_seconds / counted, 2) if counted else 0, 'tasks': tasks, 'reconstructed': True}] if tasks else []


def normalize_scored(folder_name, raw, scored):
    if scored:
        if isinstance(scored, list) and scored and isinstance(scored[0], dict) and scored[0].get('model'):
            return scored
        model = infer_model_name(folder_name, scored, raw)
        return [{'model': model, 'total_score': sum((t.get('score') or 0) for t in scored if isinstance(t, dict)), 'avg_seconds': round(sum((t.get('seconds') or 0) for t in scored if isinstance(t, dict)) / max(len(scored), 1), 2), 'tasks': scored, 'reconstructed': False}]
    return synthesize_scored_from_raw(raw, folder_name)


def canonical_model_name(name, run_name=''):
    value = (name or '').strip()
    low = value.lower()
    run_low = (run_name or '').lower()
    if 'qwenglm9' in run_low or 'glm51-distill' in low or 'qwen3.5-9b' in low:
        return 'Jackrong/MLX-Qwen3.5-9B-GLM5.1-Distill'
    if 'bonsai' in low:
        return 'prism-ml/Ternary-Bonsai-1.7B-mlx-2bit'
    if 'minimax' in low:
        return 'JANGQ-AI/MiniMax-M2.7-JANGTQ'
    if 'supergemma' in low or 'sgemma-e4b' in low:
        return 'Jiunsong/supergemma4-e4b-abliterated-mlx'
    if 'gemma4:31b' in low or 'gemma-4-31b' in low:
        return 'mlx-community/gemma-4-31b-it-4bit'
    if 'gemma4:26b' in low or 'gemma-4-26b' in low:
        return 'mlx-community/gemma-4-26b-a4b-it-4bit'
    if 'qwen36-msq' in low or '4.4bit-msq' in low:
        return 'mlx-community/Qwen3.6-35B-A3B-4.4bit-msq'
    if 'qwen36-4bit' in low or (('qwen3.6-35b-a3b-4bit' in low) and 'dwq' not in low and 'msq' not in low):
        return 'mlx-community/Qwen3.6-35B-A3B-4bit'
    if 'dwq' in low:
        return 'mlx-community/Qwen3.6-35B-A3B-4bit-DWQ'
    if value == 'Qwen3.6-35B-A3B':
        return 'mlx-community/Qwen3.6-35B-A3B-4bit'
    return value


def is_full_suite_run(run_name):
    return 'full-suite' in (run_name or '')


def task_order_key(task):
    tid = (task.get('task') or task.get('id') or '').lower()
    short = (task.get('short') or '').lower()
    order = {
        't1_json_extract': 0, 'json': 0,
        't2_routing': 1, 'route': 1,
        't3_reasoning': 2, 'reason': 2,
        't4_summary': 3, 'summary': 3,
        't5_follow_instructions': 4, 'instr': 4,
    }
    return order.get(tid, order.get(short, 99))


def build_index(data):
    models = []
    timeline = []
    task_stats = defaultdict(lambda: {'runs': 0, 'score': 0, 'max_score': 0, 'pass_count': 0})
    best_by_model = {}
    for run in data:
        run_name = run['name']
        for scored in run.get('scored', []):
            raw_model_name = scored.get('model') or run_name
            model_name = canonical_model_name(raw_model_name, run_name)
            tasks = sorted((scored.get('tasks') or []), key=task_order_key)
            total_score = scored.get('total_score') if scored.get('total_score') is not None else sum((t.get('score') or 0) for t in tasks)
            max_score = sum((t.get('max_score') or 25) for t in tasks) or max(len(tasks), 1) * 25
            pct = round((total_score / max_score) * 100, 1) if max_score else 0
            latency = scored.get('avg_seconds') or 0
            light_tasks = []
            for task in tasks:
                response = (task.get('response') or '')
                light_tasks.append({**task, 'response': response[:1200]})
            is_cloud = any(t.get('cloud') for t in run.get('raw', []) if isinstance(t, dict))
            row = {'model': model_name, 'runId': run_name, 'date': run_name[:10], 'score': total_score, 'maxScore': max_score, 'percentage': pct, 'avgLatency': latency, 'taskCount': len(tasks), 'reconstructed': bool(scored.get('reconstructed')), 'isCloud': is_cloud, 'tasks': light_tasks}
            timeline.append({'runId': run_name, 'date': run_name[:10], 'model': model_name, 'score': total_score, 'maxScore': max_score, 'percentage': pct, 'avgLatency': latency})
            current = best_by_model.get(model_name)
            candidate_key = (
                2 if 'v3' in run_name else (1 if 'full-suite' in run_name else 0),
                len(tasks),
                run_name[:10],
                total_score,
            )
            current_key = None
            if current:
                current_key = (
                    2 if 'v3' in current['runId'] else (1 if 'full-suite' in current['runId'] else 0),
                    current.get('taskCount', 0),
                    current.get('date', ''),
                    current.get('score', 0),
                )
            if current is None or candidate_key > current_key:
                best_by_model[model_name] = row
            for task in tasks:
                task_id = task.get('task') or task.get('id') or 'unknown'
                stat = task_stats[task_id]
                stat['runs'] += 1
                stat['score'] += task.get('score') or 0
                ms = task.get('max_score') or 25
                stat['max_score'] += ms
                if (task.get('score') or 0) >= ms:
                    stat['pass_count'] += 1
    models = sorted(best_by_model.values(), key=lambda x: (-x['percentage'], x['avgLatency'], x['model']))
    for item in task_stats.values():
        item['avg_pct'] = round((item['score'] / item['max_score']) * 100, 1) if item['max_score'] else 0
        item['pass_rate'] = round((item['pass_count'] / item['runs']) * 100, 1) if item['runs'] else 0
    return {'models': models, 'timeline': sorted(timeline, key=lambda x: (x['date'], x['percentage']), reverse=True), 'tasks': [{'task': k, **v} for k, v in sorted(task_stats.items())]}


socketserver.TCPServer.allow_reuse_address = True
class Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, payload):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def _send_html(self, html):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(html.encode())

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/benchmarks':
            import os, json
            suite_json_path = os.path.join(DIRECTORY, '../benchmark-suite-v3/suite.json')
            try:
                with open(suite_json_path) as f:
                    local_suite = json.load(f)
            except:
                local_suite = SUITE_PAYLOAD

            data = []
            for folder in glob.glob(os.path.join(DIRECTORY, '*')):
                if os.path.isdir(folder):
                    b_name = os.path.basename(folder)
                    if 'Bonsai-demo' in folder:
                        continue
                    b_data = {'name': b_name, 'raw': [], 'scored': [], 'summary': ''}
                    raw_path = os.path.join(folder, 'results-raw.json')
                    scored_path = os.path.join(folder, 'results-scored.json')
                    readme_path = os.path.join(folder, 'README.md')
                    if os.path.exists(raw_path):
                        with open(raw_path, 'r') as f:
                            try:
                                b_data['raw'] = json.load(f)
                            except:
                                pass
                    if os.path.exists(scored_path):
                        with open(scored_path, 'r') as f:
                            try:
                                b_data['scored'] = json.load(f)
                            except:
                                pass
                    if os.path.exists(readme_path):
                        with open(readme_path, 'r') as f:
                            b_data['summary'] = f.read()
                    b_data['scored'] = normalize_scored(b_name, b_data['raw'], b_data['scored'])
                    if b_data['raw'] or b_data['scored']:
                        data.append(b_data)
            # Trim huge responses before sending to keep payload small
            for run in data:
                for item in run.get('raw', []):
                    if isinstance(item, dict) and len(str(item.get('response', ''))) > 1200:
                        item['response'] = str(item['response'])[:1200] + '...[truncated]'
                for scored_entry in run.get('scored', []):
                    for task in (scored_entry.get('tasks', []) if isinstance(scored_entry, dict) else []):
                        if isinstance(task, dict) and len(str(task.get('response', ''))) > 1200:
                            task['response'] = str(task['response'])[:1200] + '...[truncated]'
            self._send_json({'runs': data, 'index': build_index(data), 'suite': local_suite})
            return
        if parsed.path == '/' or parsed.path == '/tests' or parsed.path.startswith('/model/'):
            self._send_html(INDEX_HTML)
            return
        self.send_response(404)
        self.end_headers()

with socketserver.TCPServer(('', PORT), Handler) as httpd:
    print(f'Serving at port {PORT}')
    httpd.serve_forever()
