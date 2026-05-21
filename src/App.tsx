import {
  Check,
  Database,
  Download,
  FolderPlus,
  Loader2,
  Mic2,
  Play,
  RefreshCw,
  Save,
  SlidersHorizontal,
  Sparkles,
  Upload
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  audioUrl,
  createProject,
  createVoice,
  exportProject,
  getJob,
  getModelStatus,
  getProject,
  listProjects,
  listVoices,
  saveScript,
  selectClip,
  startGenerate,
  updateLine
} from "./api";
import type { ExportResult, GenerationControls, GenerationJob, ModelStatus, Project, ScriptLine, VoiceProfile } from "./types";

const defaultControls: GenerationControls = {
  speed: 1,
  pitchSemitones: 0,
  gainDb: 0,
  emotionHint: "",
  pauseMs: 120,
  seed: null,
  variants: 2
};

export default function App() {
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [scriptText, setScriptText] = useState("");
  const [controls, setControls] = useState<GenerationControls>(defaultControls);
  const [defaultVoiceId, setDefaultVoiceId] = useState("");
  const [status, setStatus] = useState("准备就绪");
  const [error, setError] = useState("");
  const [exportResult, setExportResult] = useState<ExportResult | null>(null);
  const [newProjectName, setNewProjectName] = useState("剪辑补录项目");
  const [voiceForm, setVoiceForm] = useState({
    name: "",
    referenceText: "",
    consentNote: "",
    trimStartMs: 0,
    trimDurationMs: 10000
  });
  const [voiceFile, setVoiceFile] = useState<File | null>(null);

  const selectedVoice = useMemo(() => voices.find((voice) => voice.id === defaultVoiceId), [defaultVoiceId, voices]);
  const isGenerating = job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "error") {
      if (job?.status === "done" && project) {
        void refreshProject(project.id);
      }
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const nextJob = await getJob(job.id);
        setJob(nextJob);
        if ((nextJob.status === "done" || nextJob.status === "error") && project) {
          setStatus(nextJob.status === "done" ? "生成完成" : "生成遇到错误");
          setError(nextJob.errors[0] ?? "");
          await refreshProject(project.id);
        }
      } catch (err) {
        setError(`后端暂时没有响应：${String((err as Error).message ?? err)}`);
      }
    }, 900);
    return () => window.clearInterval(timer);
  }, [job, project]);

  async function refreshAll() {
    try {
      setError("");
      const [nextModel, nextVoices, nextProjects] = await Promise.all([getModelStatus(), listVoices(), listProjects()]);
      setModel(nextModel);
      setVoices(nextVoices);
      setProjects(nextProjects);
      if (!defaultVoiceId && nextVoices[0]) {
        setDefaultVoiceId(nextVoices[0].id);
      }
      if (!project && nextProjects[0]) {
        await refreshProject(nextProjects[0].id);
      }
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function refreshProject(projectId: string) {
    const nextProject = await getProject(projectId);
    setProject(nextProject);
    setProjects((items) => {
      const exists = items.some((item) => item.id === nextProject.id);
      return exists ? items.map((item) => (item.id === nextProject.id ? nextProject : item)) : [nextProject, ...items];
    });
  }

  async function handleCreateProject() {
    try {
      setError("");
      const nextProject = await createProject(newProjectName);
      setProject(nextProject);
      setProjects((items) => [nextProject, ...items.filter((item) => item.id !== nextProject.id)]);
      setStatus("项目已创建");
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function handleCreateVoice() {
    if (!voiceFile) {
      setError("请选择参考音频文件。");
      return;
    }
    if (!voiceForm.referenceText.trim()) {
      setError("请填写参考文本，而且要和参考音频逐字对应。");
      return;
    }
    try {
      setError("");
      setStatus("正在导入声音");
      const voice = await createVoice({
        file: voiceFile,
        name: voiceForm.name || voiceFile.name.replace(/\.[^.]+$/, ""),
        referenceText: voiceForm.referenceText,
        language: "Chinese",
        consentNote: voiceForm.consentNote,
        trimStartMs: voiceForm.trimStartMs,
        trimDurationMs: voiceForm.trimDurationMs
      });
      setVoices((items) => [voice, ...items]);
      if (!defaultVoiceId) {
        setDefaultVoiceId(voice.id);
      }
      setVoiceFile(null);
      setVoiceForm({ name: "", referenceText: "", consentNote: "", trimStartMs: 0, trimDurationMs: 10000 });
      setStatus("声音已入库");
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function handleSaveScript() {
    if (!project) {
      setError("请先创建项目。");
      return;
    }
    try {
      setError("");
      const nextProject = await saveScript(project.id, scriptText, defaultVoiceId, controls);
      setProject(nextProject);
      setStatus(`已保存 ${nextProject.lines.length} 行脚本`);
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function handleGenerate() {
    if (!project) {
      setError("请先创建项目。");
      return;
    }
    try {
      setError("");
      setExportResult(null);
      const nextJob = await startGenerate(project.id);
      setJob(nextJob);
      setStatus("生成任务已开始");
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function handleExport() {
    if (!project) {
      setError("请先创建项目。");
      return;
    }
    try {
      setError("");
      const result = await exportProject(project.id);
      setExportResult(result);
      setStatus(`已导出 ${result.count} 条音频`);
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function handleLineSave(line: ScriptLine) {
    try {
      setError("");
      const updated = await updateLine(line.id, line.voiceId, line.controls);
      setProject((current) =>
        current
          ? {
              ...current,
              lines: current.lines.map((item) => (item.id === updated.id ? { ...updated, clips: item.clips } : item))
            }
          : current
      );
      setStatus(`第 ${line.lineIndex} 行已保存`);
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function handleClipSelect(lineId: string, clipId: string) {
    try {
      await selectClip(clipId);
      setProject((current) =>
        current
          ? {
              ...current,
              lines: current.lines.map((line) => (line.id === lineId ? { ...line, selectedClipId: clipId } : line))
            }
          : current
      );
    } catch (err) {
      setError(String((err as Error).message ?? err));
    }
  }

  function updateProjectLine(lineId: string, patch: Partial<ScriptLine>) {
    setProject((current) =>
      current
        ? {
            ...current,
            lines: current.lines.map((line) => (line.id === lineId ? { ...line, ...patch } : line))
          }
        : current
    );
  }

  const jobPercent = job && job.total ? Math.round((job.progress / job.total) * 100) : 0;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>Voice Patch Studio</h1>
          <p>{model?.available ? "Qwen3-TTS / MLX" : "本地预览引擎"} · {model?.message ?? status}</p>
        </div>
        <button className="icon-button" title="刷新" onClick={() => void refreshAll()}>
          <RefreshCw size={18} />
        </button>
      </header>

      {error && <div className="banner error">{error}</div>}
      <div className="banner">{status}</div>

      <section className="workspace">
        <aside className="side-panel">
          <section className="panel">
            <div className="panel-heading">
              <Mic2 size={18} />
              <h2>声音库</h2>
            </div>
            <label>
              名称
              <input value={voiceForm.name} onChange={(event) => setVoiceForm({ ...voiceForm, name: event.target.value })} />
            </label>
            <label>
              音频
              <input type="file" accept=".wav,.mp3,.m4a,audio/*" onChange={(event) => setVoiceFile(event.target.files?.[0] ?? null)} />
            </label>
            <label>
              参考文本
              <textarea
                rows={3}
                value={voiceForm.referenceText}
                onChange={(event) => setVoiceForm({ ...voiceForm, referenceText: event.target.value })}
              />
            </label>
            <div className="two-col">
              <label>
                起点 ms
                <input
                  type="number"
                  value={voiceForm.trimStartMs}
                  onChange={(event) => setVoiceForm({ ...voiceForm, trimStartMs: Number(event.target.value) })}
                />
              </label>
              <label>
                长度 ms
                <input
                  type="number"
                  value={voiceForm.trimDurationMs}
                  onChange={(event) => setVoiceForm({ ...voiceForm, trimDurationMs: Number(event.target.value) })}
                />
              </label>
            </div>
            <label>
              授权备注
              <input value={voiceForm.consentNote} onChange={(event) => setVoiceForm({ ...voiceForm, consentNote: event.target.value })} />
            </label>
            <button className="primary" onClick={() => void handleCreateVoice()}>
              <Upload size={16} />
              导入声音
            </button>
          </section>

          <section className="voice-list">
            {voices.map((voice) => (
              <article className="voice-row" key={voice.id}>
                <strong>{voice.name}</strong>
                <span>{voice.language}</span>
              </article>
            ))}
          </section>
        </aside>

        <section className="main-panel">
          <div className="project-bar">
            <div className="project-create">
              <input value={newProjectName} onChange={(event) => setNewProjectName(event.target.value)} />
              <button onClick={() => void handleCreateProject()}>
                <FolderPlus size={16} />
                新建项目
              </button>
            </div>
            <select value={project?.id ?? ""} onChange={(event) => void refreshProject(event.target.value)}>
              <option value="" disabled>
                选择项目
              </option>
              {projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>

          <section className="panel script-panel">
            <div className="panel-heading">
              <Database size={18} />
              <h2>{project?.name ?? "项目"}</h2>
            </div>
            <textarea
              className="script-input"
              value={scriptText}
              onChange={(event) => setScriptText(event.target.value)}
              placeholder="粘贴脚本文本"
            />
            <div className="controls-grid">
              <label className="control-field">
                声音
                <select value={defaultVoiceId} onChange={(event) => setDefaultVoiceId(event.target.value)}>
                  <option value="">未选择</option>
                  {voices.map((voice) => (
                    <option key={voice.id} value={voice.id}>
                      {voice.name}
                    </option>
                  ))}
                </select>
              </label>
              <ControlSlider label="语速" min={0.55} max={1.75} step={0.05} value={controls.speed} onChange={(speed) => setControls({ ...controls, speed })} />
              <ControlSlider
                label="音高"
                min={-6}
                max={6}
                step={0.5}
                value={controls.pitchSemitones}
                onChange={(pitchSemitones) => setControls({ ...controls, pitchSemitones })}
              />
              <ControlSlider label="响度" min={-12} max={6} step={1} value={controls.gainDb} onChange={(gainDb) => setControls({ ...controls, gainDb })} />
              <ControlSlider
                label="停顿"
                min={0}
                max={2000}
                step={50}
                value={controls.pauseMs}
                onChange={(pauseMs) => setControls({ ...controls, pauseMs })}
              />
              <ControlSlider
                label="版本"
                min={1}
                max={5}
                step={1}
                value={controls.variants}
                onChange={(variants) => setControls({ ...controls, variants })}
              />
              <label className="control-field">
                情绪
                <input
                  value={controls.emotionHint}
                  onChange={(event) => setControls({ ...controls, emotionHint: event.target.value })}
                  placeholder="自然、略急、坚定、轻声"
                />
              </label>
            </div>
            <div className="toolbar">
              <button onClick={() => void handleSaveScript()}>
                <Save size={16} />
                保存脚本
              </button>
              <button className="primary" onClick={() => void handleGenerate()} disabled={!project?.lines.length || !voices.length || isGenerating}>
                {job?.status === "running" ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
                批量生成
              </button>
              <button onClick={() => void handleExport()} disabled={!project?.lines.some((line) => line.clips.length)}>
                <Download size={16} />
                导出 WAV
              </button>
            </div>
            {job && (
              <div className="job">
                <div className="progress">
                  <span style={{ width: `${jobPercent}%` }} />
                </div>
                <small>
                  {job.message} · {job.progress}/{job.total}
                </small>
                {job.errors.length > 0 && <small className="job-error">{job.errors[0]}</small>}
              </div>
            )}
            {exportResult && <div className="export-path">Manifest: {exportResult.manifestPath}</div>}
          </section>

          <section className="line-list">
            {project?.lines.map((line) => (
              <article className="line-row" key={line.id}>
                <div className="line-index">{line.lineIndex}</div>
                <div className="line-content">
                  <p>{line.text}</p>
                  <div className="line-controls">
                    <select value={line.voiceId} onChange={(event) => updateProjectLine(line.id, { voiceId: event.target.value })}>
                      <option value="">声音</option>
                      {voices.map((voice) => (
                        <option key={voice.id} value={voice.id}>
                          {voice.name}
                        </option>
                      ))}
                    </select>
                    <MiniNumber label="速" value={line.controls.speed} step={0.05} onChange={(speed) => updateProjectLine(line.id, { controls: { ...line.controls, speed } })} />
                    <MiniNumber
                      label="调"
                      value={line.controls.pitchSemitones}
                      step={0.5}
                      onChange={(pitchSemitones) => updateProjectLine(line.id, { controls: { ...line.controls, pitchSemitones } })}
                    />
                    <MiniNumber label="版" value={line.controls.variants} step={1} onChange={(variants) => updateProjectLine(line.id, { controls: { ...line.controls, variants } })} />
                    <button className="icon-button" title="保存本行" onClick={() => void handleLineSave(line)}>
                      <SlidersHorizontal size={16} />
                    </button>
                  </div>
                  {line.clips.length > 0 && (
                    <div className="clips">
                      {line.clips.map((clip) => (
                        <div className={`clip ${line.selectedClipId === clip.id ? "selected" : ""}`} key={clip.id}>
                          <button className="icon-button" title="选择候选" onClick={() => void handleClipSelect(line.id, clip.id)}>
                            {line.selectedClipId === clip.id ? <Check size={15} /> : <Play size={15} />}
                          </button>
                          <span>v{clip.variantIndex}</span>
                          <audio controls src={audioUrl(clip.audioUrl)} />
                          <small>{(clip.durationMs / 1000).toFixed(1)}s · {clip.lufs} LUFS</small>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </article>
            ))}
          </section>
        </section>
      </section>
      <footer>{selectedVoice ? `默认声音：${selectedVoice.name}` : "未导入声音"} · 本地服务</footer>
    </main>
  );
}

function ControlSlider(props: {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="control-field">
      <span>
        {props.label}
        <b>{props.value}</b>
      </span>
      <input type="range" min={props.min} max={props.max} step={props.step} value={props.value} onChange={(event) => props.onChange(Number(event.target.value))} />
    </label>
  );
}

function MiniNumber(props: { label: string; value: number; step: number; onChange: (value: number) => void }) {
  return (
    <label className="mini-number">
      {props.label}
      <input type="number" step={props.step} value={props.value} onChange={(event) => props.onChange(Number(event.target.value))} />
    </label>
  );
}
