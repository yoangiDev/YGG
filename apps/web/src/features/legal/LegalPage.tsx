import { useParams } from "react-router";

import { PageTitle } from "@/components/ui/PageTitle";

import { NotFound } from "@/app/RouteError";
import { SiteHeader } from "@/app/SiteHeader";

import { DOCUMENTS } from "./documents";
import { SiteFooter } from "./SiteFooter";

/** Terms, privacy and cookies (`/legal/:doc`): public, with no session, because they are read before signing up. */
export function LegalPage() {
  const { doc = "" } = useParams();
  const document = DOCUMENTS[doc];
  if (!document) return <NotFound />;

  return (
    <div className="flex min-h-dvh flex-col">
      <PageTitle>{document.title}</PageTitle>
      <SiteHeader />
      {/* Text only, no ads at the sides: it takes the full width, split into columns and in small type. */}
      <main id="main" className="w-full flex-1 px-4 py-6 sm:px-8">
        <h1 className="headline text-xl text-text">{document.title}</h1>
        <div className="mt-6 gap-x-12 md:columns-2 2xl:columns-3">
          {document.sections.map((section) => (
            <section key={section.heading} className="mb-6 break-inside-avoid">
              <h2 className="text-sm font-black text-text">{section.heading}</h2>
              {section.paragraphs?.map((text) => (
                <p key={text} className="mt-2 text-xs leading-relaxed text-soft">
                  {text}
                </p>
              ))}
              {section.list && (
                <ul className="mt-2 list-disc space-y-1.5 pl-4 text-xs leading-relaxed text-soft">
                  {section.list.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
