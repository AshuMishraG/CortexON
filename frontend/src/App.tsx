import {BrowserRouter, Route, Routes} from "react-router-dom";
import Home from "./pages/Home";
import {Layout} from "./pages/Layout";
import {Vault} from "./pages/Vault";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="/vault" element={<Vault />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
