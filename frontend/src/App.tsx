import { Navigate, Route, Routes } from "react-router-dom";
import { Hub } from "./pages/Hub";
import { Builder } from "./pages/Builder";
import { PlantPage } from "./pages/PlantPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/simulate" replace />} />
      <Route path="/simulate" element={<Hub />} />
      {/* Declared before :plantId so /simulate/build is not read as a plant id. */}
      <Route path="/simulate/build" element={<Builder />} />
      <Route path="/simulate/:plantId" element={<PlantPage />} />
      <Route path="*" element={<Navigate to="/simulate" replace />} />
    </Routes>
  );
}
