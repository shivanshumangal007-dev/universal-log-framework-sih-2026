import type { ReactNode } from "react";
import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import { fadeUp } from "../animations";

interface StatsCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  accent?: boolean;
}

export default function StatsCard({ title, value, icon, accent }: StatsCardProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.section
      ref={ref}
      className="rounded-lg border border-neutral-200 bg-white p-4 flex items-start justify-between"
      variants={fadeUp}
      initial="hidden"
      animate={isInView ? "show" : "hidden"}
    >
      <div className="space-y-1">
        <p className="text-xs font-medium text-neutral-500 uppercase tracking-wide">{title}</p>
        <p className={["text-2xl font-bold", accent ? "text-orange-500" : "text-neutral-900"].join(" ")}>
          {value}
        </p>
      </div>
      <div className={["rounded-lg p-2", accent ? "bg-orange-50 text-orange-500" : "bg-neutral-100 text-neutral-600"].join(" ")}>
        {icon}
      </div>
    </motion.section>
  );
}
