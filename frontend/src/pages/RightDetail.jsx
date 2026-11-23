
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ShieldCheck, Scale, Info } from "lucide-react";
import { rightsData } from "../data/rightsData";

export default function RightDetail() {
  const { topicSlug } = useParams();
  const topic = rightsData[topicSlug];

  if (!topic) {
    return (
      <div className="right-detail-page">
        <Link to="/rights" className="right-back-link">
          <ArrowLeft size={16} /> Back to Know Your Rights
        </Link>

        <div className="right-not-found">
          <Info size={30} />
          <h2>Content coming soon</h2>
          <p>
            We're preparing a clear and reliable guide for this topic.
          </p>
          <Link to="/rights">Explore other rights</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="right-detail-page">
      <Link to="/rights" className="right-back-link">
        <ArrowLeft size={16} /> Back to Know Your Rights
      </Link>

      <section className="right-detail-hero">
        <span className="rights-eyebrow">
          <ShieldCheck size={15} /> {topic.category}
        </span>

        <h1>{topic.title}</h1>
        <p>{topic.introduction}</p>
      </section>

      <div className="right-detail-content">
        <section className="right-law-card">
          <div className="right-detail-icon">
            <Scale size={21} />
          </div>
          <div>
            <span>APPLICABLE LAW</span>
            <h3>{topic.law}</h3>
          </div>
        </section>

        <section className="right-detail-section">
          <span className="rights-eyebrow">UNDERSTANDING THE LAW</span>
          <h2>Know what the law says</h2>

          <div className="right-detail-sections">
            {topic.sections.map((section, index) => (
              <article className="right-info-card" key={section.title}>
                <span className="right-info-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <h3>{section.title}</h3>
                  <p>{section.description}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="right-detail-section">
          <span className="rights-eyebrow">GETTING SUPPORT</span>
          <h2>Where can you seek help?</h2>

          <div className="right-help-card">
            <ul>
              {topic.whereToSeekHelp.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <Link to="/get-help">Explore support resources →</Link>
          </div>
        </section>

        <div className="right-legal-note">
          <Info size={18} />
          <p>
            This information is for general legal awareness and education.
            It is not a substitute for advice from a qualified legal
            professional. Laws and procedures may change.
          </p>
        </div>
      </div>
    </div>
  );
}
