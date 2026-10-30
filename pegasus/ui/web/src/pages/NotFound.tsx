import { Link } from "wouter";
import { AlertTriangle } from "lucide-react";

export default function NotFound() {
  return (
    <div className="page" style={{ display: "grid", placeItems: "center", minHeight: "60vh" }}>
      <div style={{ textAlign: "center" }}>
        <div className="empty-icon" style={{ margin: "0 auto 14px" }}>
          <AlertTriangle size={18} />
        </div>
        <h1 className="page-title" style={{ fontSize: 18 }}>Route not found</h1>
        <p className="page-sub" style={{ marginTop: 6 }}>The requested module is not part of this deployment.</p>
        <Link href="/" className="btn btn-primary btn-sm" style={{ marginTop: 16 }}>
          Back to mission control
        </Link>
      </div>
    </div>
  );
}
