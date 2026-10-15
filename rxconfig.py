import reflex as rx

config = rx.Config(
    app_name="codoc_in_vecdraw",
    plugins=[
        rx.plugins.TailwindV3Plugin(),
        rx.plugins.RadixThemesPlugin(theme=rx.theme(appearance="light")),
    ],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
