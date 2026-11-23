
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Search,
  ShieldCheck,
  Heart,
  BriefcaseBusiness,
  Smartphone,
  Users,
  ChevronRight,
  Scale,
} from "lucide-react";

const rightsCategories = [
  {
    id: "safety",
    title: "Safety & Protection",
    description: "Legal protection against violence, abuse and harassment.",
    icon: ShieldCheck,
    color: "rose",
    topics: [
      "Protection from Domestic Violence",
      "Protection from Dowry Harassment",
      "Protection from Sexual Harassment",
      "Protection from Stalking",
    ],
  },
  {
    id: "workplace",
    title: "Workplace Rights",
    description: "Understand your rights as a woman at work.",
    icon: BriefcaseBusiness,
    color: "purple",
    topics: [
      "Prevention of Sexual Harassment at Workplace",
      "Maternity Benefits",
      "Equal Remuneration",
    ],
  },
  {
    id: "family",
    title: "Family & Marriage",
    description: "Know the laws concerning marriage and family matters.",
    icon: Heart,
    color: "pink",
    topics: [
      "Right to Maintenance",
      "Marriage and Divorce",
      "Property and Inheritance Rights",
    ],
  },
  {
    id: "digital",
    title: "Digital Safety",
    description: "Legal safeguards against online abuse and cybercrime.",
    icon: Smartphone,
    color: "blue",
    topics: [
      "Cyberstalking",
      "Online Harassment",
      "Image-based Abuse",
    ],
  },
  {
    id: "legal",
    title: "Legal Support",
    description: "Learn about legal aid and access to justice.",
    icon: Scale,
    color: "green",
    topics: [
      "Free Legal Aid",
      "Filing a Police Complaint",
      "Women’s Helplines",
    ],
  },
  {
    id: "general",
    title: "Constitutional Rights",
    description: "Understand the fundamental rights and protections available.",
    icon: Users,
    color: "orange",
    topics: [
      "Right to Equality",
      "Right to Life and Personal Liberty",
      "Protection against Discrimination",
    ],
  },
];

const topicSlug = (topic) =>
  topic
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

export default function KnowYourRights() {
  const [search, setSearch] = useState("");

  const filteredCategories = rightsCategories
    .map((category) => ({
      ...category,
      topics: category.topics.filter((topic) =>
        topic.toLowerCase().includes(search.toLowerCase())
      ),
    }))
    .filter(
      (category) =>
        category.title.toLowerCase().includes(search.toLowerCase()) ||
        category.description.toLowerCase().includes(search.toLowerCase()) ||
        category.topics.length > 0
    );

  return (
    <div className="rights-page">
      <section className="rights-hero">
        <div className="rights-hero-content">
          <span className="rights-eyebrow">
            <ShieldCheck size={15} /> KNOW YOUR RIGHTS
          </span>

          <h1>
            Knowledge is your
            <span> strongest protection.</span>
          </h1>

          <p>
            Explore your legal rights as a woman in India. Understand the
            protections available to you and know where to turn for help.
          </p>

          <div className="rights-search">
            <Search size={19} />
            <input
              type="text"
              placeholder="Search rights, laws or topics..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <span className="rights-search-hint">
            Explore topics such as workplace safety, domestic violence and
            legal aid.
          </span>
        </div>
      </section>

      <section className="rights-content">
        <div className="rights-section-heading">
          <div>
            <span className="rights-eyebrow">EXPLORE BY CATEGORY</span>
            <h2>Understand your rights</h2>
            <p>Choose a topic to start learning.</p>
          </div>
          <span className="rights-count">
            {filteredCategories.length} categories
          </span>
        </div>

        <div className="rights-grid">
          {filteredCategories.map((category) => {
            const Icon = category.icon;

            return (
              <article className="rights-card" key={category.id}>
                <div className={`rights-card-icon ${category.color}`}>
                  <Icon size={22} />
                </div>

                <h3>{category.title}</h3>
                <p>{category.description}</p>

                <div className="rights-topics">
                  {category.topics.map((topic) => (
                    <Link
                      to={`/rights/${topicSlug(topic)}`}
                      className="rights-topic"
                      key={topic}
                    >
                      <span>{topic}</span>
                      <ChevronRight size={16} />
                    </Link>
                  ))}
                </div>
              </article>
            );
          })}
        </div>

        {filteredCategories.length === 0 && (
          <div className="rights-empty">
            <Search size={28} />
            <h3>No matching topics found</h3>
            <p>Try searching with a different keyword.</p>
          </div>
        )}
      </section>
    </div>
  );
}
