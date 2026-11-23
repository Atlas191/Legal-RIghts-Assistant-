
import {
  Phone,
  ShieldAlert,
  Scale,
  HeartHandshake,
  Globe,
  ExternalLink,
  ArrowUpRight,
  MessageCircle,
  LockKeyhole,
} from "lucide-react";

const emergencyContacts = [
  {
    name: "Emergency Response",
    number: "112",
    description: "Police, fire and ambulance assistance during emergencies.",
    icon: ShieldAlert,
    primary: true,
  },
  {
    name: "Women Helpline",
    number: "181",
    description: "24-hour support, information and referrals for women in distress.",
    icon: HeartHandshake,
  },
  {
    name: "NCW Women Helpline",
    number: "14490",
    description: "Support and referrals for women facing violence or seeking assistance.",
    icon: Phone,
  },
  {
    name: "NALSA Legal Aid",
    number: "15100",
    description: "Contact the National Legal Services Authority for legal aid and assistance.",
    icon: Scale,
  },
  {
    name: "Cyber Crime Helpline",
    number: "1930",
    description: "Report cybercrime and seek assistance with cyber-related financial fraud.",
    icon: LockKeyhole,
  },
  {
    name: "Child Helpline",
    number: "1098",
    description: "Support and assistance for children in need of care and protection.",
    icon: HeartHandshake,
  },
];

const onlineResources = [
  {
    title: "National Commission for Women",
    description:
      "Learn about the NCW and access its complaint and support services.",
    url: "https://www.ncw.gov.in/",
    label: "Visit NCW",
  },
  {
    title: "Mission Shakti",
    description:
      "Find government support services, One Stop Centres and women-focused schemes.",
    url: "https://missionshakti.wcd.gov.in/",
    label: "Visit Mission Shakti",
  },
  {
    title: "National Legal Services Authority",
    description:
      "Explore free legal aid, legal services institutions and access-to-justice resources.",
    url: "https://nalsa.gov.in/",
    label: "Visit NALSA",
  },
  {
    title: "National Cyber Crime Reporting Portal",
    description:
      "Submit complaints related to cybercrime through the official government portal.",
    url: "https://cybercrime.gov.in/",
    label: "Report cybercrime",
  },
  {
    title: "SHe-Box",
    description:
      "Access the government portal for complaints concerning sexual harassment at the workplace.",
    url: "https://shebox.wcd.gov.in/",
    label: "Visit SHe-Box",
  },
];

export default function GetHelp() {
  return (
    <div className="get-help-page">
      <section className="help-hero">
        <div className="help-hero-content">
          <span className="rights-eyebrow">
            <HeartHandshake size={15} /> SUPPORT & ASSISTANCE
          </span>

          <h1>
            You don't have to
            <span> face it alone.</span>
          </h1>

          <p>
            Find helplines, legal assistance and trusted support services.
            Help is available, and taking the first step matters.
          </p>

          <a href="tel:112" className="help-emergency-button">
            <Phone size={18} />
            Call Emergency Helpline 112
            <ArrowUpRight size={17} />
          </a>
        </div>
      </section>

      <main className="help-content">
        <section className="help-section">
          <div className="help-section-heading">
            <div>
              <span className="rights-eyebrow">IMPORTANT CONTACTS</span>
              <h2>Helplines you can reach</h2>
              <p>Choose the service that best matches your situation.</p>
            </div>
          </div>

          <div className="help-contact-grid">
            {emergencyContacts.map((contact) => {
              const Icon = contact.icon;

              return (
                <article
                  className={`help-contact-card ${
                    contact.primary ? "primary" : ""
                  }`}
                  key={contact.number}
                >
                  <div className="help-contact-top">
                    <div className="help-contact-icon">
                      <Icon size={21} />
                    </div>
                    {contact.primary && (
                      <span className="help-emergency-tag">EMERGENCY</span>
                    )}
                  </div>

                  <h3>{contact.name}</h3>
                  <p>{contact.description}</p>

                  <div className="help-contact-bottom">
                    <strong>{contact.number}</strong>
                    <a
                      href={`tel:${contact.number}`}
                      aria-label={`Call ${contact.name}`}
                    >
                      <Phone size={16} />
                      Call
                    </a>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="help-section">
          <div className="help-section-heading">
            <div>
              <span className="rights-eyebrow">ONLINE SUPPORT</span>
              <h2>Government resources</h2>
              <p>Official portals for information, complaints and assistance.</p>
            </div>
          </div>

          <div className="help-resource-list">
            {onlineResources.map((resource) => (
              <article className="help-resource-card" key={resource.title}>
                <div className="help-resource-icon">
                  <Globe size={20} />
                </div>

                <div className="help-resource-info">
                  <h3>{resource.title}</h3>
                  <p>{resource.description}</p>
                </div>

                <a
                  href={resource.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {resource.label}
                  <ExternalLink size={15} />
                </a>
              </article>
            ))}
          </div>
        </section>

        <section className="help-safety-card">
          <div className="help-safety-icon">
            <LockKeyhole size={23} />
          </div>
          <div>
            <h2>Think about your digital safety</h2>
            <p>
              If someone monitors your phone or browsing activity, consider
              using a trusted device when seeking help. Be careful when
              saving contact details, browsing history or sensitive documents.
            </p>
          </div>
        </section>

        <section className="help-bottom-note">
          <MessageCircle size={18} />
          <p>
            If you are in immediate danger, contact emergency services at
            112. Helpline availability and services may vary by location.
            If one service cannot help, try another appropriate official
            support channel.
          </p>
        </section>
      </main>
    </div>
  );
}
