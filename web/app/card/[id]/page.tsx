import { notFound } from "next/navigation";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";
import HealthCard from "@/components/HealthCard";
import PersonaSwitcher from "@/components/PersonaSwitcher";
import { getAssessment, getPersonaIds, getPersonas } from "@/lib/data";

export function generateStaticParams() {
  return getPersonaIds().map((id) => ({ id }));
}

export default function CardPage({ params }: { params: { id: string } }) {
  const assessment = getAssessment(params.id);
  if (!assessment) notFound();
  const personas = getPersonas();

  return (
    <>
      <SiteHeader active="card" />
      <main className="relative z-[2] mx-auto max-w-5xl px-5 py-8">
        <div className="mb-6">
          <span className="eyebrow mb-3 block text-ink-faint">
            Switch persona — same deterministic engine, frozen inputs
          </span>
          <PersonaSwitcher personas={personas} activeId={params.id} />
        </div>
        <HealthCard a={assessment} />
      </main>
      <SiteFooter />
    </>
  );
}
