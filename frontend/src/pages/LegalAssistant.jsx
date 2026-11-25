import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  BookOpen,
  ShieldCheck,
  UserRound,
  LoaderCircle,
  RotateCcw,
  MapPin,
  ListChecks,
  HelpCircle,
} from "lucide-react";
import {
  askLegalAssistant,
  deleteSession,
  getExamples,
} from "../services/api";

const FALLBACK_EXAMPLES = [
  {
    label: "Domestic violence",
    query: "What are my rights if I face domestic violence?",
  },
  {
    label: "Harassment at work",
    query: "My boss keeps touching me at work",
  },
  {
    label: "Dowry demands",
    query: "My husband's family keeps demanding more dowry",
  },
  {
    label: "Free legal aid",
    query: "I can't afford a lawyer",
  },
];

export default function LegalAssistant() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [needsInfo, setNeedsInfo] = useState([]);
  const [examples, setExamples] = useState(FALLBACK_EXAMPLES);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    async function loadExamples() {
      try {
        const data = await getExamples();
        if (!cancelled && Array.isArray(data?.examples) && data.examples.length > 0) {
          setExamples(data.examples);
        }
      } catch {
        // Keep fallback examples when backend is offline on initial render
      }
    }
    loadExamples();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(text = input) {
    const question = text.trim();

    if (!question || loading) return;

    setError("");
    setInput("");
    setMessages((current) => [
      ...current,
      { role: "user", content: question },
    ]);
    setLoading(true);

    try {
      const data = await askLegalAssistant(question, sessionId);

      if (data?.session_id) {
        setSessionId(data.session_id);
      }

      setNeedsInfo(Array.isArray(data?.needs_info) ? data.needs_info : []);

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: typeof data?.answer === "string" ? data.answer : "",
          off_topic: Boolean(data?.off_topic),
          fallback: Boolean(data?.fallback),
          verified: Boolean(data?.verified),
          sources: Array.isArray(data?.sources) ? data.sources : [],
          routing: Array.isArray(data?.routing) ? data.routing : [],
          roadmap: Array.isArray(data?.roadmap) ? data.roadmap : [],
          disclaimer: typeof data?.disclaimer === "string" ? data.disclaimer : "",
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  async function startNewConversation() {
    const activeSessionId = sessionId;
    setMessages([]);
    setError("");
    setInput("");
    setSessionId(null);
    setNeedsInfo([]);

    if (activeSessionId) {
      try {
        await deleteSession(activeSessionId);
      } catch {
        // Local state is already cleared
      }
    }
  }

  return (
    <div className="assistant-page">
      <div className="assistant-heading">
        <div>
          <span className="section-eyebrow">HERE TO HELP YOU</span>
          <h1>Legal Assistant</h1>
          <p>
            Ask questions about your legal rights and explore possible next
            steps under Indian law.
          </p>
        </div>

        <button
          className="clear-chat-button"
          onClick={startNewConversation}
          disabled={(messages.length === 0 && !sessionId && needsInfo.length === 0) || loading}
        >
          <RotateCcw size={15} />
          New conversation
        </button>
      </div>

      <div className="chat-panel">
        <div className="chat-topbar">
          <div className="assistant-identity">
            <div className="assistant-avatar">
              <Bot size={21} />
            </div>
            <div>
              <strong>HerRights Assistant</strong>
              <span>
                <i /> Legal information support
              </span>
            </div>
          </div>

          <div className="privacy-label">
            <ShieldCheck size={15} />
            <span>Informational support</span>
          </div>
        </div>

        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="chat-welcome">
              <div className="welcome-icon">
                <BookOpen size={27} />
              </div>
              <h2>How can I help you today?</h2>
              <p>
                You can describe a situation or ask a question about your
                rights. You don&apos;t need to share your name or identifying
                details.
              </p>

              <div className="suggestion-heading">
                <span>EXAMPLE QUESTIONS</span>
              </div>

              <div className="suggestion-grid">
                {examples.map((example) => (
                  <button
                    key={`${example.label}-${example.query}`}
                    type="button"
                    className="suggestion-card"
                    onClick={() => {
                      setInput(example.query);
                      inputRef.current?.focus();
                    }}
                    disabled={loading}
                  >
                    <div>
                      {example.label && (
                        <small className="suggestion-label">{example.label}</small>
                      )}
                      <span>{example.query}</span>
                    </div>
                    <ArrowUp size={16} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message, index) => (
                <div
                  className={`message-row ${message.role}`}
                  key={`${message.role}-${index}`}
                >
                  <div className="message-avatar">
                    {message.role === "assistant" ? (
                      <Bot size={18} />
                    ) : (
                      <UserRound size={17} />
                    )}
                  </div>

                  <div className="message-content">
                    <span className="message-author">
                      {message.role === "assistant" ? "HerRights" : "You"}
                    </span>

                    {message.role === "user" && (
                      <div className="message-bubble">{message.content}</div>
                    )}

                    {message.role === "assistant" && message.off_topic && (
                      <div className="message-bubble refusal-bubble">
                        {message.content}
                      </div>
                    )}

                    {message.role === "assistant" &&
                      !message.off_topic &&
                      message.fallback && (
                        <div className="message-bubble fallback-notice">
                          I could not write a verified explanation, so here are
                          the legal sections I found.
                        </div>
                      )}

                    {message.role === "assistant" &&
                      !message.off_topic &&
                      !message.fallback && (
                        <div className="message-bubble">{message.content}</div>
                      )}

                    {message.role === "assistant" &&
                      !message.off_topic &&
                      message.sources?.length > 0 && (
                        <div className="sources-panel">
                          <strong>
                            <BookOpen size={15} />
                            Sources and references
                          </strong>

                          {message.sources.map((source, sourceIndex) => (
                            <div
                              className="source-item"
                              key={source.id || sourceIndex}
                            >
                              <div className="source-body">
                                <b>{source.heading}</b>
                                {source.act && (
                                  <div className="source-subtitle">
                                    {source.act}
                                  </div>
                                )}
                                <div className="source-meta">
                                  {source.section && (
                                    <span className="source-label">
                                      {source.section}
                                    </span>
                                  )}
                                  {source.formerly_ipc && (
                                    <span className="source-label">
                                      {`Formerly IPC: ${source.formerly_ipc}`}
                                    </span>
                                  )}
                                </div>
                                {source.text && (
                                  <details className="source-details">
                                    <summary>Read section text</summary>
                                    <p>{source.text}</p>
                                  </details>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                    {message.role === "assistant" &&
                      !message.off_topic &&
                      message.routing?.length > 0 && (
                        <div className="sources-panel routing-panel">
                          <strong>
                            <MapPin size={15} />
                            Where to go
                          </strong>

                          <div className="routing-grid">
                            {message.routing.map((forum, forumIndex) => (
                              <div
                                className="routing-card"
                                key={`${forum.kb_ref}-${forum.name}-${forumIndex}`}
                              >
                                <b>{forum.name}</b>
                                <p>{forum.why}</p>
                                {forum.time_limit && (
                                  <span className="time-limit-badge">
                                    {`Time limit: ${forum.time_limit}`}
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                    {message.role === "assistant" &&
                      !message.off_topic &&
                      message.roadmap?.length > 0 && (
                        <div className="sources-panel roadmap-panel">
                          <strong>
                            <ListChecks size={15} />
                            Step-by-step roadmap
                          </strong>

                          <div className="roadmap-steps">
                            {message.roadmap.map((stepObj) => (
                              <div
                                className="roadmap-step"
                                key={`${stepObj.step}-${stepObj.title}`}
                              >
                                <b>{`${stepObj.step}. ${stepObj.title}`}</b>
                                {Array.isArray(stepObj.actions) &&
                                  stepObj.actions.length > 0 && (
                                    <ul className="roadmap-actions">
                                      {stepObj.actions.map(
                                        (action, actionIndex) => (
                                          <li key={actionIndex}>
                                            <span>{action.text}</span>
                                            {action.time_limit && (
                                              <span className="time-limit-badge">
                                                {`Time limit: ${action.time_limit}`}
                                              </span>
                                            )}
                                            {action.basis ===
                                              "general_guidance" && (
                                              <span className="guidance-badge">
                                                General guidance, not a legal
                                                requirement
                                              </span>
                                            )}
                                          </li>
                                        )
                                      )}
                                    </ul>
                                  )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                    {message.role === "assistant" && message.disclaimer && (
                      <p className="response-disclaimer">
                        {message.disclaimer}
                      </p>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="message-row assistant">
                  <div className="message-avatar">
                    <Bot size={18} />
                  </div>
                  <div className="message-content">
                    <span className="message-author">HerRights</span>
                    <div className="typing-indicator">
                      <LoaderCircle size={16} className="spin-icon" />
                      Thinking... this can take up to 20 seconds
                    </div>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}

          {error && (
            <div className="chat-error" role="alert">
              {error}
            </div>
          )}
        </div>

        {needsInfo.length > 0 && (
          <div className="needs-info-banner" role="status">
            <div className="needs-info-title">
              <HelpCircle size={15} />
              <strong>Follow-up question to narrow down your options</strong>
            </div>
            <ul>
              {needsInfo.map((question, idx) => (
                <li key={idx}>{question}</li>
              ))}
            </ul>
          </div>
        )}

        <form
          className="chat-input-area"
          onSubmit={(event) => {
            event.preventDefault();
            sendMessage();
          }}
        >
          <div className="chat-input-wrap">
            <textarea
              ref={inputRef}
              value={input}
              maxLength={1000}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Describe your situation or ask a legal question..."
              rows={2}
              disabled={loading}
              aria-label="Your legal question"
            />

            <button
              className="send-button"
              type="submit"
              disabled={!input.trim() || loading}
              aria-label="Send message"
            >
              <ArrowUp size={19} />
            </button>
          </div>

          <div className="input-footer">
            <span>Press Enter to send · Shift + Enter for a new line</span>
            <span>{input.length}/1000</span>
          </div>
        </form>
      </div>

      <div className="assistant-disclaimer">
        <ShieldCheck size={18} />
        <p>
          <strong>Please remember:</strong> HerRights provides legal
          information, not professional legal advice. For urgent danger,
          contact emergency services or a trusted support organisation.
        </p>
      </div>
    </div>
  );
}
