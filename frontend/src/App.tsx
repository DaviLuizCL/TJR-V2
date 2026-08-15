import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { Header } from "./components/Header";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LancamentoFormPage } from "./features/arbitragem/LancamentoFormPage";
import { PartidaScorerPage } from "./features/arbitragem/PartidaScorerPage";
import { LoginPage } from "./features/auth/LoginPage";
import { EquipeListPage } from "./features/equipe/EquipeListPage";
import { EquipeSubmissoesPage } from "./features/equipe/EquipeSubmissoesPage";
import { EventoSelectPage } from "./features/evento/EventoSelectPage";
import { FichaDashboardPage } from "./features/ficha/FichaDashboardPage";
import { FichaEditorPage } from "./features/ficha/FichaEditorPage";
import { FichaListPage } from "./features/ficha/FichaListPage";
import { FichaPreviewPage } from "./features/ficha/FichaPreviewPage";
import { HorarioPage } from "./features/horario/HorarioPage";
import { PontuarRoutePage } from "./features/arbitragem/PontuarRoutePage";
import { ConfrontoHubPage } from "./features/modalidade/ConfrontoHubPage";
import { IndividualHubPage } from "./features/modalidade/IndividualHubPage";
import { InscricaoPage } from "./features/modalidade/InscricaoPage";
import { PainelPage } from "./features/painel/PainelPage";
import { ModalidadeListPage } from "./features/modalidade/ModalidadeListPage";
import { ModalidadeWizardPage } from "./features/modalidade/ModalidadeWizardPage";
import { RodadaListPage } from "./features/modalidade/RodadaListPage";
import { RodadaSubmissoesPage } from "./features/modalidade/RodadaSubmissoesPage";
import { RankingPage } from "./features/ranking/RankingPage";
import { UsuarioListPage } from "./features/usuario/UsuarioListPage";

function AppLayout() {
  return (
    <ProtectedRoute>
      <Header />
      <Outlet />
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/eventos/:eventoId/ranking" element={<RankingPage />} />

      <Route element={<AppLayout />}>
        <Route path="/eventos" element={<EventoSelectPage />} />
        <Route
          path="/usuarios"
          element={
            <ProtectedRoute papeisPermitidos={["COORDENADOR"]}>
              <UsuarioListPage />
            </ProtectedRoute>
          }
        />
        <Route path="/equipes" element={<EquipeListPage />} />
        <Route path="/equipes/:equipeId/submissoes" element={<EquipeSubmissoesPage />} />
        <Route path="/eventos/:eventoId/modalidades" element={<ModalidadeListPage />} />
        <Route path="/eventos/:eventoId/modalidades/novo" element={<ModalidadeWizardPage />} />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/editar"
          element={<ModalidadeWizardPage />}
        />
        <Route path="/eventos/:eventoId/fichas" element={<FichaDashboardPage />} />
        <Route path="/eventos/:eventoId/individual" element={<IndividualHubPage />} />
        <Route path="/eventos/:eventoId/combates" element={<ConfrontoHubPage />} />
        <Route path="/eventos/:eventoId/painel" element={<PainelPage />} />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/horarios"
          element={<HorarioPage />}
        />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/pontuar"
          element={<PontuarRoutePage />}
        />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/fichas"
          element={<FichaListPage />}
        />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/inscricoes"
          element={<InscricaoPage />}
        />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/rodadas"
          element={<RodadaListPage />}
        />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/rodadas/:rodadaId/lancamentos/novo"
          element={<LancamentoFormPage />}
        />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/rodadas/:rodadaId/partidas/:partidaId/pontuar"
          element={<PartidaScorerPage />}
        />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/rodadas/:rodadaId/submissoes"
          element={<RodadaSubmissoesPage />}
        />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/fichas/:fichaId/editar"
          element={
            <ProtectedRoute papeisPermitidos={["COORDENADOR"]}>
              <FichaEditorPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/eventos/:eventoId/modalidades/:modalidadeId/fichas/:fichaId/preview"
          element={<FichaPreviewPage />}
        />
      </Route>

      <Route path="*" element={<Navigate to="/eventos" replace />} />
    </Routes>
  );
}
