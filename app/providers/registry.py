"""Chooses the provider for a mode: live -> Campay production, test -> simulated (or Campay demo)."""
from __future__ import annotations

from app.config import Settings
from app.providers.base import Provider, ProviderAuthError
from app.providers.campay import CampayProvider
from app.providers.simulated import SimulatedProvider


class ProviderNotConfigured(ProviderAuthError):
    pass


class ProviderRegistry:
    def __init__(self, settings: Settings):
        self._s = settings
        self._cache: dict[str, Provider] = {}

    def provider_name(self, mode: str) -> str:
        if mode == "test" and self._s.test_provider == "simulated":
            return "simulated"
        return "campay"

    def for_mode(self, mode: str) -> Provider:
        if mode in self._cache:
            return self._cache[mode]
        s = self._s
        if mode == "live":
            if not (s.campay_live_username and s.campay_live_password):
                raise ProviderNotConfigured("live provider is not configured")
            provider: Provider = CampayProvider(
                base_url=s.campay_live_base_url,
                username=s.campay_live_username,
                password=s.campay_live_password,
                webhook_key=s.campay_live_webhook_key,
            )
        elif mode == "test":
            if s.test_provider == "simulated":
                provider = SimulatedProvider()
            else:
                if not (s.campay_demo_username and s.campay_demo_password):
                    raise ProviderNotConfigured("campay demo provider is not configured")
                provider = CampayProvider(
                    base_url=s.campay_demo_base_url,
                    username=s.campay_demo_username,
                    password=s.campay_demo_password,
                    webhook_key=s.campay_demo_webhook_key,
                )
        else:
            raise ValueError(f"unknown mode {mode}")
        self._cache[mode] = provider
        return provider

    def campay_verifiers(self) -> list[tuple[str, Provider]]:
        """(mode, provider) pairs able to verify inbound Campay webhooks."""
        pairs: list[tuple[str, Provider]] = []
        if self._s.campay_live_webhook_key and self._s.campay_live_username:
            pairs.append(("live", self.for_mode("live")))
        if self._s.test_provider == "campay_demo" and self._s.campay_demo_webhook_key:
            pairs.append(("test", self.for_mode("test")))
        return pairs

    async def aclose(self) -> None:
        for provider in self._cache.values():
            await provider.aclose()
