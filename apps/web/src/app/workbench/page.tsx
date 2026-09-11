import { redirect } from "next/navigation";

/** Legacy route — the workbench is the console. */
export default function WorkbenchRedirect() {
  redirect("/console/home");
}
