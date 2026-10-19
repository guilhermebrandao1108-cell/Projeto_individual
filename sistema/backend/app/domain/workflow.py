"""Ticket state machine.

Requirement from the case study: "responder" is not "resolver". Staff can only
*propose* a solution (RESOLVIDO); the ticket is closed (FECHADO) only when the
customer confirms it. Rejecting the solution reopens the ticket.

    ABERTO ──iniciar──▶ EM_ATENDIMENTO ◀──resposta do cliente── AGUARDANDO_CLIENTE
      │                   │    ▲  └──────pedir_info──────────────────▶ │
      │                   │    └──────────rejeitar──────┐              │
      └──propor_solucao───┴─────propor_solucao────▶ RESOLVIDO ◀────────┘
                                                        │
                                                    confirmar
                                                        ▼
                                                     FECHADO
"""
from enum import StrEnum

from ..models import Role, Status
from . import DomainError, PermissionDenied


class Action(StrEnum):
    INICIAR = 'iniciar'
    PEDIR_INFO = 'pedir_info'
    RESPOSTA_CLIENTE = 'resposta_cliente'
    PROPOR_SOLUCAO = 'propor_solucao'
    CONFIRMAR = 'confirmar'
    REJEITAR = 'rejeitar'


STAFF = frozenset({Role.ATENDENTE, Role.GESTOR})
CUSTOMER = frozenset({Role.CLIENTE})

# action -> (allowed source statuses, target status, roles allowed to perform it)
TRANSITIONS: dict[Action, tuple[frozenset[Status], Status, frozenset[Role]]] = {
    Action.INICIAR: (frozenset({Status.ABERTO}), Status.EM_ATENDIMENTO, STAFF),
    Action.PEDIR_INFO: (frozenset({Status.EM_ATENDIMENTO}), Status.AGUARDANDO_CLIENTE, STAFF),
    Action.RESPOSTA_CLIENTE: (frozenset({Status.AGUARDANDO_CLIENTE}), Status.EM_ATENDIMENTO, CUSTOMER),
    Action.PROPOR_SOLUCAO: (frozenset({Status.ABERTO, Status.EM_ATENDIMENTO, Status.AGUARDANDO_CLIENTE}), Status.RESOLVIDO, STAFF),
    Action.CONFIRMAR: (frozenset({Status.RESOLVIDO}), Status.FECHADO, CUSTOMER),
    Action.REJEITAR: (frozenset({Status.RESOLVIDO}), Status.EM_ATENDIMENTO, CUSTOMER),
}


def next_status(current: Status, action: Action, role: Role) -> Status:
    sources, target, roles = TRANSITIONS[action]
    if role not in roles:
        raise PermissionDenied(f'Perfil {role} não pode executar "{action}"')
    if current not in sources:
        raise DomainError(f'Não é possível "{action}" um chamado com status "{current}"')
    return target


def allowed_actions(current: Status, role: Role) -> list[Action]:
    """What the UI may offer to this user right now (RESPOSTA_CLIENTE is implicit on reply)."""
    return [a for a, (sources, _, roles) in TRANSITIONS.items()
            if current in sources and role in roles and a != Action.RESPOSTA_CLIENTE]
