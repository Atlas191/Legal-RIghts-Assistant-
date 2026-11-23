import { Link } from "react-router-dom";
import {
  ArrowRight,
  MessageCircle,
  BookOpen,
  ShieldCheck,
  HandHelping,
  Sparkles,
} from "lucide-react";

const features = [
  {
    icon: MessageCircle,
    title: "AI Legal Assistant",
    description:
      "Describe your situation and explore relevant laws and possible next steps.",
    link: "/assistant",
    action: "Start a conversation",
  },
  {
    icon: BookOpen,
    title: "Know Your Rights",
    description:
      "Understand important laws and legal protections in simple language.",
    link: "/rights",
    action: "Explore your rights",
  },
  {
    icon: HandHelping,
    title: "Get Help",
    description:
      "Find helplines, legal aid resources and useful support services.",
    link: "/get-help",
    action: "Find support",
  },
];

export default function Home() {
  return (
    <div className="home-page">
      <section className="hero-section">
        <div className="hero-content">
          <div className="eyebrow">
            <Sparkles size={15} />
            <span>KNOW YOUR RIGHTS. KNOW YOUR POWER.</span>
          </div>

          <h1>
            Justice begins with
            <br />
            <span>knowing your rights.</span>
          </h1>

          <p>
            A safe space to understand your legal rights, explore Indian laws,
            and discover the support available to you.
          </p>

          <div className="hero-actions">
            <Link to="/assistant" className="primary-button">
              Talk to Legal Assistant <ArrowRight size={17} />
            </Link>

            <Link to="/rights" className="secondary-button">
              Explore your rights
            </Link>
          </div>

          <div className="hero-note">
            <ShieldCheck size={17} />
            <span>Designed for accessible legal awareness and guidance</span>
          </div>
        </div>

        <div className="hero-visual">
          <div className="visual-circle circle-one" />
          <div className="visual-circle circle-two" />

          <div className="visual-card">
            <div className="visual-card-icon">
              <ShieldCheck size={34} />
            </div>
            <span className="visual-card-label">YOUR RIGHTS MATTER</span>
            <h2>Knowledge is your first step towards empowerment.</h2>
            <div className="visual-card-line" />
            <p>Awareness · Support · Empowerment</p>
          </div>

          <div className="floating-tag">
            <BookOpen size={17} />
            <span>Understand the law</span>
          </div>
        </div>
      </section>

      <section className="features-section">
        <div className="section-heading">
          <div>
            <span className="section-eyebrow">EXPLORE THE PLATFORM</span>
            <h2>How can we help you today?</h2>
            <p>Start with the support or information you need.</p>
          </div>
        </div>

        <div className="feature-grid">
          {features.map(({ icon: Icon, title, description, link, action }) => (
            <article className="feature-card" key={title}>
              <div className="feature-icon">
                <Icon size={23} />
              </div>

              <h3>{title}</h3>
              <p>{description}</p>

              <Link to={link}>
                {action} <ArrowRight size={16} />
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="disclaimer">
        <ShieldCheck size={20} />
        <p>
          <strong>Important:</strong> This platform provides legal awareness
          and informational assistance. It does not replace advice from a
          qualified legal professional.
        </p>
      </section>
    </div>
  );
}