import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  Panel,
  StatusDot,
  Tag,
  Button,
  Kpi,
  Tabs,
  Progress,
  Ring,
  EmptyState,
  ErrorState,
  timeAgo,
} from "@/components/ui/primitives";

describe("UI Primitives", () => {
  it("renders Panel with title and content", () => {
    render(<Panel title="System Status"><p>All systems nominal</p></Panel>);
    expect(screen.getByText("System Status")).toBeDefined();
    expect(screen.getByText("All systems nominal")).toBeDefined();
  });

  it("renders Button and handles click events", () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Acknowledge</Button>);
    const btn = screen.getByRole("button", { name: "Acknowledge" });
    expect(btn).toBeDefined();
    fireEvent.click(btn);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("renders StatusDot with appropriate state class", () => {
    const { container } = render(<StatusDot state="ok" />);
    const dot = container.querySelector(".cs-dot--ok");
    expect(dot).not.toBeNull();
  });

  it("renders Tag with custom tone", () => {
    render(<Tag tone="warn">Warning State</Tag>);
    expect(screen.getByText("Warning State")).toBeDefined();
  });

  it("renders Kpi with label and value", () => {
    render(<Kpi label="Vibration RMS" value="1.2 mm/s" state="ok" />);
    expect(screen.getByText("Vibration RMS")).toBeDefined();
    expect(screen.getByText("1.2 mm/s")).toBeDefined();
  });

  it("renders Tabs and triggers onChange callback", () => {
    const handleChange = vi.fn();
    const tabs = [
      { id: "tab1", label: "Overview" },
      { id: "tab2", label: "Sensors", count: 4 },
    ];
    render(<Tabs tabs={tabs} active="tab1" onChange={handleChange} />);
    expect(screen.getByText("Overview")).toBeDefined();
    expect(screen.getByText("Sensors")).toBeDefined();
    expect(screen.getByText("4")).toBeDefined();

    fireEvent.click(screen.getByText("Sensors"));
    expect(handleChange).toHaveBeenCalledWith("tab2");
  });

  it("renders Progress and Ring with numeric bounds", () => {
    render(<Progress value={75} tone="ok" />);
    const progressbar = screen.getByRole("progressbar");
    expect(progressbar.getAttribute("aria-valuenow")).toBe("75");

    render(<Ring value={92} tone="cyan" label="Health 92%" />);
    const ring = screen.getByRole("img", { name: "Health 92%" });
    expect(ring).toBeDefined();
    expect(screen.getByText("92")).toBeDefined();
  });

  it("renders EmptyState and ErrorState correctly", () => {
    render(<EmptyState title="No Records" detail="Nothing found in this view." />);
    expect(screen.getByText("No Records")).toBeDefined();
    expect(screen.getByText("Nothing found in this view.")).toBeDefined();

    const handleRetry = vi.fn();
    render(<ErrorState message="Network error occurred" onRetry={handleRetry} />);
    expect(screen.getByText("Something went wrong")).toBeDefined();
    expect(screen.getByText("Network error occurred")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it("formats relative timestamps correctly with timeAgo", () => {
    const now = new Date().toISOString();
    expect(timeAgo(now)).toBe("now");

    const tenMinsAgo = new Date(Date.now() - 10 * 60 * 1000).toISOString();
    expect(timeAgo(tenMinsAgo)).toBe("10m ago");

    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    expect(timeAgo(twoHoursAgo)).toBe("2h ago");
  });
});
