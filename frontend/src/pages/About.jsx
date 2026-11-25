
import {
  ShieldCheck,
  Scale,
  HeartHandshake,
  MessageCircle,
  FileText,
  BookOpen,
  Target,
  Lightbulb,
  Code2,
  Heart,
  ArrowUpRight,
} from "lucide-react";

const features = [
  {
    icon: MessageCircle,
    title: "AI Legal Assistant",
    description:
      "Ask questions about legal situations and receive structured information about relevant Indian laws and possible next steps.",
  },
  {
    icon: BookOpen,
    title: "Know Your Rights",
    description:
      "Explore simplified information about women's legal rights, important legislation and available protections.",
  },
  {
    icon: HeartHandshake,
    title: "Access to Support",
    description:
      "Find important helplines, government portals and legal assistance resources in one place.",
  },
  {
    icon: FileText,
    title: "Document Assistance",
    description:
      "Support the preparation of structured complaint documents and access saved documents.",
  },
];

const technologies = [
  "React",
  "JavaScript",
  "HTML5",
  "CSS3",
  "Python",
  "FastAPI",
  "ChromaDB",
  "Hugging Face",
  "Ollama",
];

export default function About() {
  return (
    <div className="about-page">
      {/* Hero */}
      <section className="about-hero">
        <div className="about-hero-content">
          <span className="rights-eyebrow">
            <Heart size={15} /> ABOUT HER RIGHTS
          </span>

          <h1>
            Making legal awareness
            <span> accessible to everyone.</span>
          </h1>

          <p>
            HerRights is a technology-driven initiative designed to simplify
            legal awareness and help women in India understand their rights,
            explore available protections and find the support they need.
          </p>

          <a href="#our-mission" className="about-hero-link">
            Discover our mission <ArrowUpRight size={17} />
          </a>
        </div>
      </section>

      {/* Introduction */}
      <section className="about-intro" id="our-mission">
        <div className="about-intro-heading">
          <span className="rights-eyebrow">WHY HER RIGHTS EXISTS</span>
          <h2>Legal knowledge should never be out of reach.</h2>
        </div>

        <div className="about-intro-text">
          <p>
            Understanding the law can be difficult. Legal language,
            complicated procedures and limited awareness can make it
            challenging for people to understand their rights or identify
            where to seek help.
          </p>

          <p>
            HerRights aims to bridge this gap by bringing legal information,
            AI-assisted guidance and support resources together in a simple,
            accessible platform.
          </p>
        </div>
      </section>

      {/* Mission and Vision */}
      <section className="about-purpose">
        <article className="about-purpose-card mission">
          <div className="about-purpose-icon">
            <Target size={23} />
          </div>
          <span>OUR MISSION</span>
          <h2>Simplifying access to legal awareness.</h2>
          <p>
            To make information about women's legal rights easier to
            understand and help users discover relevant laws, protections
            and support services.
          </p>
        </article>

        <article className="about-purpose-card vision">
          <div className="about-purpose-icon">
            <Lightbulb size={23} />
          </div>
          <span>OUR VISION</span>
          <h2>A more informed and empowered society.</h2>
          <p>
            To contribute towards a society where individuals can better
            understand their legal rights and make informed decisions
            about seeking assistance.
          </p>
        </article>
      </section>

      {/* Features */}
      <section className="about-features">
        <div className="about-section-heading">
          <span className="rights-eyebrow">WHAT WE OFFER</span>
          <h2>One platform, multiple ways to find support.</h2>
          <p>
            HerRights brings together tools and resources designed to
            make legal information more approachable.
          </p>
        </div>

        <div className="about-feature-grid">
          {features.map((feature) => {
            const Icon = feature.icon;

            return (
              <article className="about-feature-card" key={feature.title}>
                <div className="about-feature-icon">
                  <Icon size={22} />
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </article>
            );
          })}
        </div>
      </section>

      {/* Technology */}
      <section className="about-tech">
        <div className="about-tech-heading">
          <div className="about-tech-icon">
            <Code2 size={24} />
          </div>
          <span className="rights-eyebrow">BUILT WITH TECHNOLOGY</span>
          <h2>Technology behind HerRights</h2>
          <p>
            The platform combines modern web technologies with AI and
            information retrieval techniques to make legal information
            easier to explore.
          </p>
        </div>

        <div className="about-tech-tags">
          {technologies.map((technology) => (
            <span key={technology}>{technology}</span>
          ))}
        </div>
      </section>

      {/* SDG */}
      <section className="about-impact">
        <span className="rights-eyebrow">OUR BROADER IMPACT</span>
        <h2>Contributing towards a better future.</h2>
        <p>
          HerRights aligns with the United Nations Sustainable Development
          Goals by promoting awareness, access to information and equality.
        </p>

        <div className="about-sdg-grid">
          <article className="about-sdg-card">
            <div className="about-sdg-number">05</div>
            <div>
              <span>UNITED NATIONS SDG 5</span>
              <h3>Gender Equality</h3>
              <p>
                Supporting awareness of women's rights and contributing
                towards gender equality and empowerment.
              </p>
            </div>
          </article>

          <article className="about-sdg-card">
            <div className="about-sdg-number">16</div>
            <div>
              <span>UNITED NATIONS SDG 16</span>
              <h3>Peace, Justice and Strong Institutions</h3>
              <p>
                Promoting access to legal information and awareness of
                justice-related support systems.
              </p>
            </div>
          </article>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="about-disclaimer">
        <ShieldCheck size={24} />
        <div>
          <h3>Important legal disclaimer</h3>
          <p>
            HerRights is an educational and legal awareness platform.
            Information provided through the platform is for general
            informational purposes and does not constitute professional
            legal advice. Users should consult a qualified legal
            professional for advice regarding their individual situations.
          </p>
        </div>
      </section>

      <footer className="about-footer">
        <div className="about-footer-brand">
          <Scale size={19} />
          <strong>HerRights</strong>
        </div>
        <p>Legal support, simplified.</p>
      </footer>
    </div>
  );
}
