"use client";

import { useState } from "react";
import styles from "./styles.module.scss";
import Link from "next/link";

export default function LearnMorePage() {
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({
    name: "",
    address: "",
    phone: "",
    referrer: "",
  });

  const onChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className={styles.wrapper}>
      <div className={styles.card}>
        {!submitted ? (
          <>
            <h1 className={styles.title}>Tell us about you</h1>
            <p className={styles.subtitle}>We’ll be in touch shortly.</p>

            <form onSubmit={onSubmit} className={styles.form}>
              <label className={styles.label}>
                <span>Name</span>
                <input
                  name="name"
                  type="text"
                  required
                  value={form.name}
                  onChange={onChange}
                  placeholder="Jane Doe"
                />
              </label>

              <label className={styles.label}>
                <span>Address</span>
                <input
                  name="address"
                  type="text"
                  required
                  value={form.address}
                  onChange={onChange}
                  placeholder="123 Main St, City, State"
                />
              </label>

              <label className={styles.label}>
                <span>Phone number</span>
                <input
                  name="phone"
                  type="tel"
                  inputMode="tel"
                  required
                  value={form.phone}
                  onChange={onChange}
                  placeholder="(555) 555-5555"
                />
              </label>

              <label className={styles.label}>
                <span>Where did you hear about us?</span>
                <input
                  name="referrer"
                  type="text"
                  value={form.referrer}
                  onChange={onChange}
                  placeholder="Search, referral, conference, etc."
                />
              </label>

              <button type="submit" className={styles.submit} disabled={submitting}>
                {submitting ? "Submitting..." : "Submit"}
              </button>
            </form>

            <div className={styles.backLink}>
              <Link href="/">← Back to site</Link>
            </div>
          </>
        ) : (
          <div className={styles.thanks}>
            <h2>Thanks — we’ve got your info!</h2>
            <p>We’ll reach out shortly to schedule a demo.</p>
            <div className={styles.backLink}>
              <Link href="/">Return home</Link>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
