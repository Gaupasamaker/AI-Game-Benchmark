"""
Sistema Anti-Trampas.
Timeouts, validación de acciones y penalizaciones.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ViolationRecord:
    """Registro de violación de reglas."""
    player_id: str
    violation_type: str  # "timeout", "invalid_action", "exception"
    tick: int
    details: str = ""


@dataclass
class AntiCheatConfig:
    """Configuración del sistema anti-trampas."""
    timeout_ms: float = 30.0  # Timeout por acción en ms
    max_violations: int = 10  # Violaciones máximas antes de descalificación
    penalty_per_violation: float = 0.01  # Penalización de reward
    strict_mode: bool = False  # Si True, descalifica al primer error


class AntiCheat:
    """
    Sistema anti-trampas para partidas.
    
    Valida timeouts, acciones y aplica penalizaciones.
    """
    
    def __init__(self, config: AntiCheatConfig | None = None):
        self.config = config or AntiCheatConfig()
        self.violations: list[ViolationRecord] = []
        self.violation_count: dict[str, int] = {}
    
    def reset(self) -> None:
        """Reinicia el registro de violaciones."""
        self.violations = []
        self.violation_count = {}
    
    def timed_call(
        self, 
        player_id: str, 
        func: Callable, 
        *args, 
        tick: int = 0,
        **kwargs
    ) -> tuple[Any, bool]:
        """
        Ejecuta una función con timeout.
        
        Returns:
            (resultado, exito): resultado de la función y si se completó a tiempo
        """
        start = time.perf_counter()
        
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            if elapsed_ms > self.config.timeout_ms:
                self._record_violation(
                    player_id, 
                    "timeout", 
                    tick,
                    f"Tardó {elapsed_ms:.2f}ms (límite: {self.config.timeout_ms}ms)"
                )
                return result, False
            
            return result, True
            
        except Exception as e:
            self._record_violation(
                player_id,
                "exception",
                tick,
                str(e)
            )
            return None, False
    
    def validate_action(
        self, 
        player_id: str, 
        action: dict, 
        valid_actions: list[dict],
        tick: int = 0
    ) -> tuple[dict, bool]:
        """
        Valida una acción contra las acciones válidas.
        
        Returns:
            (acción_a_usar, es_válida): Si inválida, retorna no-op
        """
        if action in valid_actions:
            return action, True
        
        self._record_violation(
            player_id,
            "invalid_action",
            tick,
            f"Acción inválida: {action}"
        )
        
        # Retornar no-op o primera acción válida
        return valid_actions[0] if valid_actions else {}, False
    
    def _record_violation(
        self, 
        player_id: str, 
        violation_type: str, 
        tick: int,
        details: str
    ) -> None:
        """Registra una violación."""
        self.violations.append(ViolationRecord(
            player_id=player_id,
            violation_type=violation_type,
            tick=tick,
            details=details
        ))
        self.violation_count[player_id] = self.violation_count.get(player_id, 0) + 1
    
    def is_disqualified(self, player_id: str) -> bool:
        """Verifica si un jugador está descalificado."""
        count = self.violation_count.get(player_id, 0)
        
        if self.config.strict_mode and count > 0:
            return True
        
        return count >= self.config.max_violations
    
    def get_penalty(self, player_id: str) -> float:
        """Obtiene penalización acumulada para un jugador."""
        count = self.violation_count.get(player_id, 0)
        return count * self.config.penalty_per_violation
    
    def get_violations(self, player_id: str | None = None) -> list[ViolationRecord]:
        """Obtiene violaciones, opcionalmente filtradas por jugador."""
        if player_id is None:
            return self.violations
        return [v for v in self.violations if v.player_id == player_id]
    
    def to_dict(self) -> dict:
        """Serializa para JSON."""
        return {
            "config": {
                "timeout_ms": self.config.timeout_ms,
                "max_violations": self.config.max_violations,
                "strict_mode": self.config.strict_mode
            },
            "violations": [
                {
                    "player_id": v.player_id,
                    "type": v.violation_type,
                    "tick": v.tick,
                    "details": v.details
                }
                for v in self.violations
            ],
            "violation_counts": self.violation_count
        }
