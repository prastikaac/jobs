import sys

file_path = r'c:\Users\Ac\Documents\Programming\HTML CSS JS\JobsInFinland\scraper\job_template.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

c1_s = '''                              <bdi class="pDt pIn">
                                <time class="aTtmp pTtmp upd" data-date="Published:" data-text="{-scraped_at-}"></time>
                              </bdi>'''
c1_r = '''                              <bdi class="pDt pIn">
                                <time class="aTtmp pTtmp upd">Published: {-scraped_at-}</time>
                              </bdi>'''
content = content.replace(c1_s, c1_r)

c2_s = '''                                <bdi class="admN" data-text="Prasiddha Acharya" data-write="Posted by"></bdi>'''
c2_r = '''                                <bdi class="admN"><span class="admnname">Posted by : </span>Prasiddha Acharya</bdi>'''
content = content.replace(c2_s, c2_r)

c3_s = '''                          <div class="pSh">
                            <div class="pShc" data-text="&nbsp; Share :">
                              <a id="fb" href="#" target="_blank" aria-label="Facebook" class="longbtns c fb"
                                data-text="Share" rel="noopener" role="button"> <span class="dispc">&nbsp;</span>
                                <svg viewBox="0 0 64 64">
                                  <path
                                    d="M20.1,36h3.4c0.3,0,0.6,0.3,0.6,0.6V58c0,1.1,0.9,2,2,2h7.8c1.1,0,2-0.9,2-2V36.6c0-0.3,0.3-0.6,0.6-0.6h5.6 c1,0,1.9-0.7,2-1.7l1.3-7.8c0.2-1.2-0.8-2.4-2-2.4h-6.6c-0.5,0-0.9-0.4-0.9-0.9v-5c0-1.3,0.7-2,2-2h5.9c1.1,0,2-0.9,2-2V6.2 c0-1.1-0.9-2-2-2h-7.1c-13,0-12.7,10.5-12.7,12v7.3c0,0.3-0.3,0.6-0.6,0.6h-3.4c-1.1,0-2,0.9-2,2v7.8C18.1,35.1,19,36,20.1,36z">
                                  </path>
                                </svg>
                              </a>
                              <a aria-label="Whatsapp" class="longbtns c wa" data-text="Share" id="wa" href="#"
                                rel="noopener" role="button" target="_blank"> <span class="dispc">&nbsp;</span>
                                <svg viewBox="0 0 64 64">
                                  <path
                                    d="M6.9,48.4c-0.4,1.5-0.8,3.3-1.3,5.2c-0.7,2.9,1.9,5.6,4.8,4.8l5.1-1.3c1.7-0.4,3.5-0.2,5.1,0.5 c4.7,2.1,10,3,15.6,2.1c12.3-1.9,22-11.9,23.5-24.2C62,17.3,46.7,2,28.5,4.2C16.2,5.7,6.2,15.5,4.3,27.8c-0.8,5.6,0,10.9,2.1,15.6 C7.1,44.9,7.3,46.7,6.9,48.4z M21.3,19.8c0.6-0.5,1.4-0.9,1.8-0.9s2.3-0.2,2.9,1.2c0.6,1.4,2,4.7,2.1,5.1c0.2,0.3,0.3,0.7,0.1,1.2 c-0.2,0.5-0.3,0.7-0.7,1.1c-0.3,0.4-0.7,0.9-1,1.2c-0.3,0.3-0.7,0.7-0.3,1.4c0.4,0.7,1.8,2.9,3.8,4.7c2.6,2.3,4.9,3,5.5,3.4 c0.7,0.3,1.1,0.3,1.5-0.2c0.4-0.5,1.7-2,2.2-2.7c0.5-0.7,0.9-0.6,1.6-0.3c0.6,0.2,4,1.9,4.7,2.2c0.7,0.3,1.1,0.5,1.3,0.8 c0.2,0.3,0.2,1.7-0.4,3.2c-0.6,1.6-2.1,3.1-3.2,3.5c-1.3,0.5-2.8,0.7-9.3-1.9c-7-2.8-11.8-9.8-12.1-10.3c-0.3-0.5-2.8-3.7-2.8-7.1 C18.9,22.1,20.7,20.4,21.3,19.8z">
                                  </path>
                                </svg>
                              </a>
                              <a aria-label="X / Twitter" style="background: #000000;" class="longbtns c tw"
                                data-text="Tweet" id="tw" href="#" rel="noopener" role="button" target="_blank"> <span
                                  class="dispc">&nbsp;</span>
                                <svg viewBox="0 0 1200 1227" width="32" height="32" xmlns="http://www.w3.org/2000/svg"
                                  fill="currentColor">
                                  <path
                                    d="M714.3 543.7 1175.2 0h-107.5L662.7 447.9 293.3 0H0l490.4 630.1 0 0L0 1227h107.5l437-494.7 387.4 494.7H1200zM200.6 82.1h74.2l722.9 933.7h-74.2z" />
                                </svg>

                              </a>

                              <label style="cursor: pointer;" aria-label="Share to other apps" for="forShare">
                                <svg viewBox="0 0 512 512">
                                  <path
                                    d="M417.4,224H288V94.6c0-16.9-14.3-30.6-32-30.6c-17.7,0-32,13.7-32,30.6V224H94.6C77.7,224,64,238.3,64,256 c0,17.7,13.7,32,30.6,32H224v129.4c0,16.9,14.3,30.6,32,30.6c17.7,0,32-13.7,32-30.6V288h129.4c16.9,0,30.6-14.3,30.6-32 C448,238.3,434.3,224,417.4,224z">
                                  </path>
                                </svg>
                              </label>
                            </div>
                          </div>'''
c3_r = '''                          <div class="pSh">
                            <div class="pShc">Share :
                              <a translate="no" aria-label="Facebook" class="longbtns c fb" href="#" id="fb"
                                rel="noopener" role="button" target="_blank"><svg viewbox="0 0 64 64">
                                  <path
                                    d="M20.1,36h3.4c0.3,0,0.6,0.3,0.6,0.6V58c0,1.1,0.9,2,2,2h7.8c1.1,0,2-0.9,2-2V36.6c0-0.3,0.3-0.6,0.6-0.6h5.6 c1,0,1.9-0.7,2-1.7l1.3-7.8c0.2-1.2-0.8-2.4-2-2.4h-6.6c-0.5,0-0.9-0.4-0.9-0.9v-5c0-1.3,0.7-2,2-2h5.9c1.1,0,2-0.9,2-2V6.2 c0-1.1-0.9-2-2-2h-7.1c-13,0-12.7,10.5-12.7,12v7.3c0,0.3-0.3,0.6-0.6,0.6h-3.4c-1.1,0-2,0.9-2,2v7.8C18.1,35.1,19,36,20.1,36z">
                                  </path>
                                </svg></a>
                              <a translate="no" aria-label="Whatsapp" class="longbtns c wa" href="#" id="wa"
                                rel="noopener" role="button" target="_blank"><svg viewbox="0 0 64 64">
                                  <path
                                    d="M6.9,48.4c-0.4,1.5-0.8,3.3-1.3,5.2c-0.7,2.9,1.9,5.6,4.8,4.8l5.1-1.3c1.7-0.4,3.5-0.2,5.1,0.5 c4.7,2.1,10,3,15.6,2.1c12.3-1.9,22-11.9,23.5-24.2C62,17.3,46.7,2,28.5,4.2C16.2,5.7,6.2,15.5,4.3,27.8c-0.8,5.6,0,10.9,2.1,15.6 C7.1,44.9,7.3,46.7,6.9,48.4z M21.3,19.8c0.6-0.5,1.4-0.9,1.8-0.9s2.3-0.2,2.9,1.2c0.6,1.4,2,4.7,2.1,5.1c0.2,0.3,0.3,0.7,0.1,1.2 c-0.2,0.5-0.3,0.7-0.7,1.1c-0.3,0.4-0.7,0.9-1,1.2c-0.3,0.3-0.7,0.7-0.3,1.4c0.4,0.7,1.8,2.9,3.8,4.7c2.6,2.3,4.9,3,5.5,3.4 c0.7,0.3,1.1,0.3,1.5-0.2c0.4-0.5,1.7-2,2.2-2.7c0.5-0.7,0.9-0.6,1.6-0.3c0.6,0.2,4,1.9,4.7,2.2c0.7,0.3,1.1,0.5,1.3,0.8 c0.2,0.3,0.2,1.7-0.4,3.2c-0.6,1.6-2.1,3.1-3.2,3.5c-1.3,0.5-2.8,0.7-9.3-1.9c-7-2.8-11.8-9.8-12.1-10.3c-0.3-0.5-2.8-3.7-2.8-7.1 C18.9,22.1,20.7,20.4,21.3,19.8z">
                                  </path>
                                </svg></a>
                              <a translate="no" aria-label="X / Twitter" class="longbtns c tw" href="#" id="tw"
                                rel="noopener" role="button" style="background: #000000;" target="_blank"><svg
                                  fill="currentColor" height="32" viewbox="0 0 1200 1227" width="32"
                                  xmlns="http://www.w3.org/2000/svg">
                                  <path
                                    d="M714.3 543.7 1175.2 0h-107.5L662.7 447.9 293.3 0H0l490.4 630.1 0 0L0 1227h107.5l437-494.7 387.4 494.7H1200zM200.6 82.1h74.2l722.9 933.7h-74.2z">
                                  </path>
                                </svg></a>
                              <label aria-label="Share to other apps" for="forShare" style="cursor: pointer;">
                                <svg viewbox="0 0 512 512">
                                  <path
                                    d="M417.4,224H288V94.6c0-16.9-14.3-30.6-32-30.6c-17.7,0-32,13.7-32,30.6V224H94.6C77.7,224,64,238.3,64,256 c0,17.7,13.7,32,30.6,32H224v129.4c0,16.9,14.3,30.6,32,30.6c17.7,0,32-13.7,32-30.6V288h129.4c16.9,0,30.6-14.3,30.6-32 C448,238.3,434.3,224,417.4,224z">
                                  </path>
                                </svg>
                              </label>
                            </div>
                          </div>'''
content = content.replace(c3_s, c3_r)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done successfully.')
