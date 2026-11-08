                    if doc.is_encrypted:
                        st.error("This PDF is password-protected. Unlock it with permission before editing.")
                    elif len(doc) == 0:
                        st.error("This PDF contains no pages.")
                    else:
                        st.caption(f"{len(doc)} page(s) · {len(pdf_bytes):,} bytes · Original file remains unchanged")
                        page_num = st.selectbox("Page to edit", list(range(1, len(doc) + 1))) - 1
                        page_image, scale = render_pdf_page(doc, page_num)
                        st.markdown("#### Select what to edit")
                        selection_mode = st.radio("Selection method", ["Click text", "Draw area"], horizontal=True,
                                                   help="Click text works on PDFs with selectable text. Draw area also works on scanned pages.")
                        if selection_mode == "Click text":
                            st.info("Click directly on a word or line in the page preview. CleanData will find the matching text span. For scanned PDFs, switch to Draw area.")
                        else:
                            st.info("Draw a rectangle over the content to replace. Everything overlapping that rectangle may be covered, so check the preview carefully.")
                        canvas_width = page_image.width
                        canvas_height = page_image.height
                        canvas_result = st_canvas(
                            fill_color="rgba(20,184,138,0.18)", stroke_width=2,
                            stroke_color="#12a981", background_image=page_image,
                            update_streamlit=True, height=canvas_height, width=canvas_width,
                            drawing_mode="point" if selection_mode == "Click text" else "rect",
                            point_display_radius=6,
                            key=f"pdf_canvas_{page_num}_{selection_mode}_{pdf_upload.name}",
                        )
                        objects = (canvas_result.json_data or {}).get("objects", []) if canvas_result else []
                        selected_box = None
                        selected_description = ""
                        if selection_mode == "Click text":
                            point_obj = next((obj for obj in reversed(objects) if obj.get("type") in ("circle", "point")), None)
                            if point_obj:
                                px = float(point_obj.get("left", 0)) + float(point_obj.get("width", 0)) / 2
                                py = float(point_obj.get("top", 0)) + float(point_obj.get("height", 0)) / 2
                                found = find_pdf_text_span(doc, page_num, px, py, scale)
                                if found:
                                    selected_description, selected_box = found
                        else:
                            rect_obj = next((obj for obj in reversed(objects) if obj.get("type") == "rect"), None)
                            if rect_obj:
                                left = float(rect_obj.get("left", 0))
                                top = float(rect_obj.get("top", 0))
                                width = float(rect_obj.get("width", 0)) * float(rect_obj.get("scaleX", 1))
                                height = float(rect_obj.get("height", 0)) * float(rect_obj.get("scaleY", 1))
                                selected_box = (left, top, left + width, top + height)
                        replacement = st.text_area("Replacement text (leave empty to remove selected content)", height=90,
                                                    placeholder="Type the replacement text…", key="pdf_replacement")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            font_size = st.slider("Font size", 6, 28, 11)
                        with col2:
                            fill_choice = st.selectbox("Cover colour", ["White", "Transparent is not supported", "Black"], index=0)
                        with col3:
                            text_choice = st.selectbox("Text colour", ["Black", "Dark blue", "Red"], index=0)
                        fill_rgb = (1, 1, 1) if fill_choice == "White" else (0, 0, 0)
                        text_rgb = {"Black": (0, 0, 0), "Dark blue": (0.05, 0.12, 0.35), "Red": (0.7, 0.05, 0.05)}[text_choice]
                        if selected_box:
                            st.caption(f"Selected: {selected_description[:120] if selected_description else 'custom page area'}")
                            if st.button("Apply replacement to PDF", type="primary"):
                                try:
                                    output_bytes = apply_pdf_replacement(pdf_bytes, page_num,
                                        selected_box, replacement, scale, float(font_size), text_rgb, fill_rgb)
                                    st.session_state.edited_pdf_bytes = output_bytes
                                    st.session_state.edited_pdf_name = safe_filename(pdf_upload.name) + "_edited.pdf"
                                    log_activity(email, "Edited PDF", f"{pdf_upload.name}, page {page_num+1}")
                                    st.success("Replacement applied to a copy of the original PDF.")
                                except Exception as exc:
                                    st.error(f"Couldn't apply this edit: {exc}")
                        else:
                            st.caption("Click a text span or draw a rectangle on the page to enable editing.")
                        if st.session_state.get("edited_pdf_bytes"):
                            st.download_button("Download edited PDF", st.session_state.edited_pdf_bytes,
                                file_name=st.session_state.get("edited_pdf_name", "edited.pdf"),
                                mime="application/pdf", type="primary")
                        with st.expander("PDF text extraction / accessibility check"):
                            extracted = "\n".join(p.get_text("text") for p in doc)
                            st.caption(f"Extractable text characters: {len(extracted):,}")
                            if not extracted.strip():
                                st.warning("This appears to be a scanned/image-only PDF. Visual redaction still works, but selecting text semantically and matching its original font requires OCR and manual review.")
                    doc.close()
                except Exception as exc:
                    st.error(f"PDF could not be opened: {exc}")

elif page == "Reports":
    st.title("Reports")
    if st.session_state.report_text:
        st.text_area("Latest data quality report", st.session_state.report_text, height=380)
        st.download_button("Download latest report", st.session_state.report_text.encode("utf-8"), "cleandata_report.txt")
    else:
        st.info("Create a report after cleaning a dataset. Reports are based on the actual file and recorded cleaning operations.")

elif page == "Account":
    st.title("Account settings")
    st.markdown("### Workspace profile")
    st.write(f"**Name:** {user['name']}")
    st.write(f"**Business:** {user['company']}")
    st.write(f"**Email:** {user['email']}")
    st.write(f"**Phone:** {user['phone']}")
    st.write(f"**Email verified:** {'Yes' if user['verified'] else 'No'}")
    st.caption("Payment activation is intentionally not triggered by a browser return URL. A production PayFast integration must validate the server-to-server ITN signature and payment status before extending access.")

st.markdown("<div class='footer'>CleanData LAI · Your data, your decisions · Review automated changes before business use</div>", unsafe_allow_html=True)
