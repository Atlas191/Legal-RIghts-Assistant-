import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  BookOpen,
  ShieldCheck,
  Plus,
  UserRound,
  ExternalLink,
  LoaderCircle,
  Trash2,
} from "lucide-react";
import { askLegalAssistant } from "../services/api";

const suggestions = [
  "What are my rights if I face domestic violence?",
  "What can I do if I experience harassment at work?",
  "What is the Dowry Prohibition Act?",
  "How can I get free legal aid in India?",
];

function getAnswer(data) {
  if (typeof data?.answer === "string") return data.answer;
  if (typeof data?.result?.answer === "string") return data.result.answer;
  return "The server responded, but its answer format wasn't recognised. Please check the backend response schema.";
}

function getSources(data) {
  if (Array.isArray(data?.sources)) return data.sources;
  if (Array.isArray(data?.result?.sources)) return data.result.sources;
  return [];
}

export default function LegalAssistant() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const [sessionId, setSessionId] = useState(null);

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

        if (data.session_id) {
        setSessionId(data.session_id);
        }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: getAnswer(data),
          sources: getSources(data),
          disclaimer: data?.disclaimer || "",
          verified: data?.verified,
          fallback: data?.fallback,
        },
      ]);
    } catch (err) {
      setError(
        err.message?.includes("Failed to fetch")
          ? "Unable to connect to the legal assistant server. Please check that the backend is running."
          : err.message || "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function clearChat() {
    setMessages([]);
    setError("");
    setInput("");
    setSessionId(null);
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
          onClick={clearChat}
          disabled={messages.length === 0 || loading}
        >
          <Trash2 size={15} />
          Clear chat
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
                rights. You don't need to share your name or identifying
                details.
              </p>

              <div className="suggestion-heading">
                <span>TRY ASKING</span>
              </div>

              <div className="suggestion-grid">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    className="suggestion-card"
                    onClick={() => sendMessage(suggestion)}
                    disabled={loading}
                  >
                    <span>{suggestion}</span>
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

                    <div className="message-bubble">
                      {message.content}
                    </div>

                    {message.role === "assistant" &&
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
                              <div>
                                <b>{source.title || source.name || "Legal source"}</b>
                                {source.section && <span>{source.section}</span>}
                                {source.excerpt && <p>{source.excerpt}</p>}
                              </div>

                              {source.url && (
                                <a
                                  href={source.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  aria-label="Open legal source"
                                >
                                  <ExternalLink size={15} />
                                </a>
                              )}
                            </div>
                          ))}
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
                      Looking into your question...
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
            <span>{input.length}/2000</span>
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