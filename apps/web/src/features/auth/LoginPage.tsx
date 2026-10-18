import { zodResolver } from "@hookform/resolvers/zod";
import { Activity, Radar, Skull } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation } from "react-router";

import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { SiteHeader } from "@/app/SiteHeader";
import { PageTitle } from "@/components/ui/PageTitle";
import { LegalLinks } from "@/features/legal/SiteFooter";

import { useAuth } from "./AuthProvider";
import { loginSchema, registerSchema } from "./schemas";

const FEATURES = [
  { icon: Radar, title: "Role-normalized radar", text: "Your metrics scored 0–100 against every rank, from Iron to Challenger." },
  { icon: Skull, title: "Death heatmaps", text: "Where and when you die, split into early game, laning and late game." },
  { icon: Activity, title: "Snapshots over time", text: "Freeze a period of games and compare it with the next one." },
];

function FormError({ message }: { message: string }) {
  return (
    <p role="alert" className="border border-stat-red/40 bg-stat-red/10 px-3 py-2 text-sm text-stat-red">
      {message}
    </p>
  );
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function SignInForm() {
  const { login } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login(values);
    } catch (error) {
      setFormError(errorMessage(error, "Could not sign in."));
    }
  });

  return (
    <form className="mt-8 flex flex-col gap-4" noValidate onSubmit={(event) => void onSubmit(event)}>
      {formError && <FormError message={formError} />}
      <Field label="Email" error={errors.email?.message}>
        {(props) => <Input {...props} type="email" autoComplete="email" {...register("email")} />}
      </Field>
      <Field label="Password" error={errors.password?.message}>
        {(props) => <Input {...props} type="password" autoComplete="current-password" {...register("password")} />}
      </Field>
      <Button type="submit" loading={isSubmitting} className="mt-2">
        Sign in
      </Button>
    </form>
  );
}

function RegisterForm() {
  const { register: createAccount } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(registerSchema), defaultValues: { username: "", email: "", password: "" } });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await createAccount(values);
    } catch (error) {
      setFormError(errorMessage(error, "Could not create the account."));
    }
  });

  return (
    <form className="mt-8 flex flex-col gap-4" noValidate onSubmit={(event) => void onSubmit(event)}>
      {formError && <FormError message={formError} />}
      <Field label="Username" error={errors.username?.message}>
        {(props) => <Input {...props} autoComplete="username" {...register("username")} />}
      </Field>
      <Field label="Email" error={errors.email?.message}>
        {(props) => <Input {...props} type="email" autoComplete="email" {...register("email")} />}
      </Field>
      <Field label="Password" error={errors.password?.message} hint="At least 10 characters.">
        {(props) => <Input {...props} type="password" autoComplete="new-password" {...register("password")} />}
      </Field>
      <Button type="submit" loading={isSubmitting} className="mt-2">
        Create account
      </Button>
    </form>
  );
}

/** Access to the public demo (API with DEMO_MODE): visible credentials and one-click entry. */
function DemoAccess() {
  const { login } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const email = import.meta.env.VITE_DEMO_EMAIL;
  const password = import.meta.env.VITE_DEMO_PASSWORD;

  if (!email || !password) return null;

  const enter = () => {
    setPending(true);
    setError(null);
    login({ email, password }).catch((reason: unknown) => {
      setError(errorMessage(reason, "The demo is not available right now."));
      setPending(false);
    });
  };

  return (
    <section aria-labelledby="demo-title" className="mt-8 border border-acid/30 bg-acid/8 p-4">
      <h3 id="demo-title" className="text-sm font-bold text-text">
        Just looking around?
      </h3>
      <p className="mt-1 text-xs text-muted">The demo account is read-only and uses seeded, anonymized games.</p>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-muted">Email</dt>
        <dd className="text-text">{email}</dd>
        <dt className="text-muted">Password</dt>
        <dd className="text-text">{password}</dd>
      </dl>
      {error && (
        <p role="alert" className="mt-3 text-xs text-stat-red">
          {error}
        </p>
      )}
      <Button variant="outline" className="mt-4 w-full" loading={pending} onClick={enter}>
        Enter the demo
      </Button>
    </section>
  );
}

export function LoginPage() {
  const { status } = useAuth();
  const location = useLocation();
  const [mode, setMode] = useState<"login" | "register">("login");

  const from = (location.state as { from?: { pathname?: string; search?: string } } | null)?.from;
  const target = from?.pathname && from.pathname !== "/login" ? `${from.pathname}${from.search ?? ""}` : "/account";

  // After signing in the AuthProvider becomes "authenticated" and this redirect does the rest.
  if (status === "authenticated") return <Navigate to={target} replace />;

  return (
    <div className="flex min-h-dvh flex-col">
    <PageTitle>{mode === "login" ? "Sign in" : "Create an account"}</PageTitle>
    <SiteHeader />
    <div className="grid flex-1 lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-line/60 p-12 lg:flex">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-40 -left-40 size-[36rem] rounded-full bg-acid/15 blur-3xl"
        />
        <div className="relative max-w-md">
          <h1 className="text-2xl leading-tight font-bold text-text">
            Find out <span className="text-acid">why</span> you win and lose.
          </h1>
          <p className="mt-4 text-muted">
            YGG reads the timeline of every ranked game and turns it into metrics a coach would look at.
          </p>
          <ul className="mt-10 flex flex-col gap-6">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-4">
                <span className="grid size-10 shrink-0 place-items-center border border-acid/30 bg-acid/10 text-acid">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <p className="font-bold text-text">{title}</p>
                  <p className="text-sm text-muted">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-muted">
          YGG is not endorsed by Riot Games and does not reflect the views of Riot Games or anyone involved in League of
          Legends.
        </p>
      </aside>

      <main className="flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm">
          <h2 className="text-xl font-bold text-text">{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="mt-1 text-sm text-muted">
            {mode === "login" ? "Sign in to see your players and analyses." : "It takes ten seconds. No Riot login needed."}
          </p>

          {mode === "login" ? <SignInForm /> : <RegisterForm />}

          <p className="mt-6 text-center text-sm text-muted">
            {mode === "login" ? "New to YGG? " : "Already have an account? "}
            <button
              type="button"
              className="-my-1.5 cursor-pointer py-1.5 font-bold text-acid hover:underline"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? "Create an account" : "Sign in instead"}
            </button>
          </p>

          {mode === "register" && (
            <p className="mt-4 text-center text-xs text-subtle">
              By creating an account you accept the{" "}
              <Link to="/legal/terms" className="text-soft underline">
                Terms
              </Link>{" "}
              and the{" "}
              <Link to="/legal/privacy" className="text-soft underline">
                Privacy Policy
              </Link>
              .
            </p>
          )}

          {mode === "login" && <DemoAccess />}

          <LegalLinks className="mt-10 flex flex-wrap justify-center gap-x-5 gap-y-2 text-xs text-subtle" />
        </div>
      </main>
    </div>
    </div>
  );
}
